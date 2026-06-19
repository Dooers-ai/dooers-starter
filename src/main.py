import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from dooers.agents.server import verify_dooers_whatsapp_tool_inbound_with_persistence
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.config import settings
from src.database import close_pool, init_pool
from src.modules.agent.agent import agent_server, dooers_agent_handler
from src.modules.helpers.speech import audio_store
from src.modules.upload.chat_upload import MAX_UPLOAD_BYTES, process_chat_upload_bytes
from src.modules.channels.whatsapp_channel import dispatch_tools_whatsapp_inbound
from src.modules.upload.settings_upload import process_settings_upload_bytes
from src.modules.services.supabase_client import get_supabase_client
from src.modules.services import tally as tally_svc
from src.modules.services import recrutamento_service as recrutamento_svc
from src.modules.services import treinamentos_service as treinamentos_svc
from src.modules.services.constants import (
    TABELA_INSCRICOES,
    TABELA_CANDIDATOS,
    RESPOSTA_PENDENTE,
)


def configure_logging() -> None:
    """Apply root level from ``LOGGING_LEVEL``; keep Azure / HTTP client libs at WARNING to avoid noisy INFO."""
    name = (settings.logging_level or "INFO").strip().upper()
    root_level = logging.INFO
    if hasattr(logging, name):
        cand = getattr(logging, name)
        if isinstance(cand, int):
            root_level = cand

    logging.basicConfig(
        level=root_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    for noisy in (
        "azure",
        "azure.core",
        "urllib3",
        "httpx",
        "httpcore",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


configure_logging()

logger = logging.getLogger(settings.api_agent_name)

API_PREFIX = settings.api_prefix


@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent_server.ensure_initialized()
    logger.info(
        "Agents SDK ingest allowlist active: %s",
        sorted(agent_server.allowed_content_types) if agent_server.allowed_content_types else None,
    )
    await init_pool()
    yield
    await close_pool()
    await agent_server.close()


app = FastAPI(
    title="WhatsApp Franquia Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter()


@api_router.get("/health")
async def health():
    return {"status": "ok"}


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
        agent_server.persistence,
        body,
        sig,
        agent_id=agent_id,
        instance_id=instance_id,
        log=logger,
    ):
        raise HTTPException(401, "invalid signature")
    if data.get("connectivity_check"):
        return {"ok": True}
    thread_id = await dispatch_tools_whatsapp_inbound(
        agent_server,
        dooers_agent_handler,
        data,
    )
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
    filename = file.filename or "upload"
    mime = file.content_type or "application/octet-stream"

    if not agent_id.strip():
        raise HTTPException(400, "agent_id is required")

    src: Literal["chat", "form"] = "form" if source == "form" else "chat"
    return await process_chat_upload_bytes(
        data=data,
        filename=filename,
        mime_type=mime,
        agent_id=agent_id,
        thread_id=thread_id.strip() or None,
        run_id=run_id.strip() or None,
        source=src,
    )


@api_router.post("/settings-upload")
async def settings_upload(
    file: UploadFile,
    field_id: str = Form(""),
    agent_id: str = Form(""),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    result = await process_settings_upload_bytes(
        data=data,
        filename=file.filename or "file",
        mime_type=file.content_type,
        agent_id=agent_id,
        field_id=field_id or None,
    )
    logger.info(
        "[settings-upload] agent=%s field=%s size=%s indexed_doc_id=%s index=%s",
        agent_id,
        field_id,
        result["size"],
        result.get("id"),
        result.get("vector_store_id"),
    )
    return result


@api_router.get("/audio/{ref_id}")
async def get_audio(ref_id: str):
    entry = audio_store.get(ref_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audio not found")
    return Response(content=entry["data"], media_type=entry["mime_type"])


# =============================================================================
# Tally Webhooks
# =============================================================================

def _verify_tally_signature(request: Request, body: bytes) -> bool:
    """Verify Tally webhook HMAC-SHA256 signature if TALLY_SIGNING_SECRET is set."""
    secret = (getattr(settings, "tally_signing_secret", None) or "").strip()
    if not secret:
        # No secret configured — accept all (development mode)
        return True
    sig_header = request.headers.get("tally-signature") or request.headers.get("x-tally-signature") or ""
    if not sig_header:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header.lower().lstrip("sha256="))


@api_router.post("/webhooks/tally/inscricao-treinamento")
async def tally_inscricao_treinamento(request: Request) -> dict:
    """Tally webhook: unit registers for a training session.

    Expected Tally form fields (mapped via parse_inscricao_treinamento):
    - unidade_id or unidade_nome, cronograma_id or treinamento_id, responsavel_nome, responsavel_telefone
    """
    body = await request.body()
    if not _verify_tally_signature(request, body):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    try:
        dados = tally_svc.parse_inscricao_treinamento(payload)
    except Exception as exc:
        logger.warning("tally_inscricao_treinamento: parse failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"parse error: {exc}")

    if not dados:
        raise HTTPException(status_code=422, detail="missing required fields")

    try:
        supabase = await get_supabase_client()
        # dados already includes resposta and arquivado from parse_inscricao_treinamento;
        # set them explicitly to ensure correct values regardless of tally field mapping.
        result = await supabase.table(TABELA_INSCRICOES).insert(
            {**dados, "resposta": RESPOSTA_PENDENTE, "arquivado": False}
        ).execute()
        inserted = (result.data or [{}])[0]
        logger.info("tally_inscricao_treinamento: criada inscricao id=%s", inserted.get("id"))
        return {"ok": True, "id": inserted.get("id")}
    except Exception:
        logger.exception("tally_inscricao_treinamento: Supabase insert failed")
        raise HTTPException(status_code=500, detail="database error")


@api_router.post("/webhooks/tally/candidatura")
async def tally_candidatura(request: Request) -> dict:
    """Tally webhook: candidate submits their application (with CV PDF link).

    Expected Tally form fields (mapped via parse_candidatura):
    - nome, email, telefone, vaga_id, pdf_url
    Triggers background CV analysis via GPT-4o after insert.
    """
    body = await request.body()
    if not _verify_tally_signature(request, body):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    try:
        dados = tally_svc.parse_candidatura(payload)
    except Exception as exc:
        logger.warning("tally_candidatura: parse failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"parse error: {exc}")

    if not dados:
        raise HTTPException(status_code=422, detail="missing required fields")

    try:
        supabase = await get_supabase_client()
        result = await supabase.table(TABELA_CANDIDATOS).insert(
            {
                **dados,
                "arquivado": False,
            }
        ).execute()
        inserted = (result.data or [{}])[0]
        candidato_id = inserted.get("id") or ""
        logger.info("tally_candidatura: criado candidato id=%s", candidato_id)

        # Trigger background PDF analysis (fire-and-forget)
        if candidato_id and dados.get("pdf_url"):
            openai_api_key = (getattr(settings, "openai_api_key", None) or "").strip()
            if openai_api_key:
                asyncio.create_task(
                    recrutamento_svc.analisar_candidaturas_em_background(
                        supabase,
                        [candidato_id],
                        openai_api_key,
                    )
                )

        return {"ok": True, "id": candidato_id}
    except Exception:
        logger.exception("tally_candidatura: Supabase insert failed")
        raise HTTPException(status_code=500, detail="database error")


@api_router.post("/webhooks/tally/comportamental")
async def tally_comportamental(request: Request) -> dict:
    """Tally webhook: candidate completes behavioral assessment form.

    Expected Tally form fields (mapped via parse_comportamental):
    - candidato_id plus behavioral assessment answers
    Generates and persists behavioral profile via GPT-4o.
    """
    body = await request.body()
    if not _verify_tally_signature(request, body):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    try:
        dados = tally_svc.parse_comportamental(payload)
    except Exception as exc:
        logger.warning("tally_comportamental: parse failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"parse error: {exc}")

    candidato_id = (dados or {}).get("candidato_id") or ""
    respostas = (dados or {}).get("respostas") or {}

    if not candidato_id or not respostas:
        raise HTTPException(status_code=422, detail="missing candidato_id or respostas")

    try:
        openai_api_key = (getattr(settings, "openai_api_key", None) or "").strip()
        perfil = ""
        if openai_api_key:
            perfil = await recrutamento_svc.gerar_perfil_comportamental(respostas, openai_api_key)

        supabase = await get_supabase_client()
        if perfil:
            await recrutamento_svc.salvar_perfil_comportamental(supabase, candidato_id, perfil)
            logger.info("tally_comportamental: perfil salvo candidato_id=%s", candidato_id)
        else:
            logger.warning("tally_comportamental: perfil vazio candidato_id=%s", candidato_id)

        return {"ok": True, "candidato_id": candidato_id, "perfil_gerado": bool(perfil)}
    except Exception:
        logger.exception("tally_comportamental: falhou candidato_id=%s", candidato_id)
        raise HTTPException(status_code=500, detail="processing error")


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    logger.info("WebSocket connection from %s:%s", client_host, client_port)
    await websocket.accept()
    try:
        await agent_server.handle(websocket, dooers_agent_handler)
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        raise
    finally:
        logger.info("WebSocket closed for %s:%s", client_host, client_port)


app.include_router(api_router, prefix=API_PREFIX)


@app.get("/")
async def root_bare():
    return {
        "service": "WhatsApp Franquia Agent",
        "version": "0.1.0",
        "api_prefix": API_PREFIX,
        "hint": f"Use routes under {API_PREFIX}/",
    }


@app.get("/health")
async def health_bare():
    return {"status": "ok"}
