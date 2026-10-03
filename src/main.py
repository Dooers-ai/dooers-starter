import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from dooers.agents.server import verify_dooers_whatsapp_tool_inbound_with_persistence
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.config import settings
from src.modules.agent.agent import agent_server, dooers_agent_handler
from src.modules.agent.schemas import settings_schema
from src.modules.channels.whatsapp_channel import dispatch_tools_whatsapp_inbound
from src.modules.doc_processing.repository import ensure_schema as ensure_documents_schema
from src.modules.helpers.speech import audio_store
from src.modules.llm.gateway_models import refresh_schema_llm_models
from src.modules.rag.knowledge_sync import install_settings_knowledge_hydrate
from src.modules.rag.service import rag_service
from src.modules.upload.chat_upload import MAX_UPLOAD_BYTES, process_chat_upload_bytes
from src.modules.upload.settings_upload import process_settings_upload_bytes
from src.modules.upload.skills_upload import process_skill_upload_bytes


def configure_logging() -> None:
    name = (settings.logging_level or "INFO").strip().upper()
    level = getattr(logging, name, logging.INFO)
    logging.basicConfig(
        level=level if isinstance(level, int) else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    for noisy in ("urllib3", "httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # The SDK auto-instruments optional vendor SDKs (anthropic, google-genai); missing ones log ERRORs.
    logging.getLogger("opentelemetry.instrumentation.instrumentor").setLevel(logging.CRITICAL)


configure_logging()
logger = logging.getLogger(settings.api_agent_name)
API_PREFIX = settings.api_prefix


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot must never crash because external infra is down: the hosted runtime needs /health to
    # answer on $PORT. Each step degrades on its own and logs what is unavailable.
    try:
        await agent_server.ensure_initialized()
        logger.info("content allow-list: %s", sorted(agent_server.allowed_content_types or []))
    except Exception:
        logger.exception("agent_server.ensure_initialized() failed — DEGRADED (chat/persistence unavailable)")
    try:
        if install_settings_knowledge_hydrate(agent_server.persistence):
            logger.info("managed RAG: %s", settings.dooers_rag_service_url)
        else:
            logger.info("managed RAG disabled (set DOOERS_RAG_SERVICE_URL + AGENT_SEED_SECRET to enable)")
    except Exception:
        logger.exception("knowledge hydrate install failed — Studio will not show the RAG inventory")
    try:
        await ensure_documents_schema()
    except Exception:
        logger.exception("document table init failed — thread documents will only live in memory")
    try:
        await refresh_schema_llm_models(settings_schema, force=True)
    except Exception:
        logger.exception("gateway model sync failed — Studio shows the default model only")
    yield
    try:
        await agent_server.close()
    except Exception:
        logger.exception("agent_server.close() failed during shutdown")


app = FastAPI(title="Dooers Agent Starter", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
api_router = APIRouter()


@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "llm": "dooers_gateway" if settings.uses_dooers_gateway else "openai",
        "rag": rag_service.pipeline,
    }


@api_router.post("/whatsapp/inbound")
async def whatsapp_tools_inbound(request: Request) -> dict:
    """HMAC (``X-WhatsApp-Tool-Signature``) — ``connectivity_check`` or ``message`` + ``content``."""
    body = await request.body()
    sig = request.headers.get("X-WhatsApp-Tool-Signature")
    data = json.loads(body.decode("utf-8") or "{}")
    agent_id = (data.get("agent_id") or "").strip()
    instance_id = (data.get("instance_id") or "").strip() or None
    await agent_server.ensure_initialized()
    if not await verify_dooers_whatsapp_tool_inbound_with_persistence(
        agent_server.persistence, body, sig, agent_id=agent_id, instance_id=instance_id, log=logger
    ):
        raise HTTPException(401, "invalid signature")
    if data.get("connectivity_check"):
        return {"ok": True}
    thread_id = await dispatch_tools_whatsapp_inbound(agent_server, dooers_agent_handler, data)
    return {"ok": True, "thread_id": thread_id}


@api_router.post("/uploads")
async def uploads(
    file: UploadFile,
    agent_id: str = Form(""),
    thread_id: str = Form(""),
    run_id: str = Form(""),
    source: str = Form("chat"),
):
    """Chat/form attachments — returns ref_id for the WebSocket message flow."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    if not agent_id.strip():
        raise HTTPException(400, "agent_id is required")
    src: Literal["chat", "form"] = "form" if source == "form" else "chat"
    return await process_chat_upload_bytes(
        data=data,
        filename=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        agent_id=agent_id,
        thread_id=thread_id.strip() or None,
        run_id=run_id.strip() or None,
        source=src,
    )


@api_router.post("/settings-upload")
async def settings_upload(file: UploadFile, field_id: str = Form(""), agent_id: str = Form("")):
    """Knowledge base files (Studio FILE_MULTI) → managed Dooers RAG."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    result = await process_settings_upload_bytes(
        data=data, filename=file.filename or "file", mime_type=file.content_type, agent_id=agent_id, field_id=field_id or None
    )
    logger.info("[settings-upload] agent=%s field=%s size=%s doc=%s", agent_id, field_id, len(data), result.get("id"))
    return result


@api_router.post("/skills-upload")
async def skills_upload(file: UploadFile, field_id: str = Form(""), agent_id: str = Form("")):
    """Skill Markdown files (Studio FILE_MULTI) — validated, stored in settings, never indexed."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    result = process_skill_upload_bytes(data=data, filename=file.filename or "skill.md", mime_type=file.content_type, agent_id=agent_id)
    logger.info("[skills-upload] agent=%s skill=%s", agent_id, result.get("skill_id"))
    return result


@api_router.get("/audio/{ref_id}")
async def get_audio(ref_id: str):
    entry = audio_store.get(ref_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audio not found")
    return Response(content=entry["data"], media_type=entry["mime_type"])


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    logger.info("WebSocket connection from %s", client)
    await websocket.accept()
    try:
        await agent_server.handle(websocket, dooers_agent_handler)
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        raise
    finally:
        logger.info("WebSocket closed for %s", client)


app.include_router(api_router, prefix=API_PREFIX)


@app.get("/")
async def root_bare():
    return {
        "service": "Dooers Agent Starter",
        "version": "0.2.0",
        "api_prefix": API_PREFIX or "/",
        "hint": f"Routes are served under {API_PREFIX or '/'} (WebSocket at {API_PREFIX}/ws).",
    }


@app.get("/health")
async def health_bare():
    return {"status": "ok"}
