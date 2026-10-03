"""/settings-upload — knowledge base files → managed Dooers RAG."""

from __future__ import annotations

from fastapi import HTTPException

from src.modules.rag.ingest_filename import validate_rag_ingest_filename
from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_ID
from src.modules.rag.service import rag_service
from src.modules.upload.chat_upload import MAX_UPLOAD_BYTES


async def process_settings_upload_bytes(*, data: bytes, filename: str, mime_type: str | None, agent_id: str, field_id: str | None) -> dict:
    if not agent_id.strip():
        raise HTTPException(400, "agent_id is required")
    validate_rag_ingest_filename(filename)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    if not data:
        raise HTTPException(400, "empty file")
    if not rag_service.enabled:
        raise HTTPException(
            status_code=503,
            detail="RAG gerenciado não configurado (defina DOOERS_RAG_SERVICE_URL e AGENT_SEED_SECRET).",
        )
    try:
        return await rag_service.ingest_bytes(
            agent_id=agent_id.strip(),
            data=data,
            filename=filename,
            mime_type=mime_type,
            field_id=(field_id or KNOWLEDGE_FIELD_ID).strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
