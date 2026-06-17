"""Shared logic for /settings-upload (knowledge base files)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException

from src.config import settings
from src.modules.agent.agent import agent_server
from src.modules.rag.service import rag_service
from src.modules.rag.ingest_filename import validate_rag_ingest_filename
from src.modules.upload.chat_upload import MAX_UPLOAD_BYTES


async def process_settings_upload_bytes(
    *,
    data: bytes,
    filename: str,
    mime_type: str | None,
    agent_id: str,
    field_id: str | None,
) -> dict:
    if not agent_id.strip():
        raise HTTPException(400, "agent_id is required")
    validate_rag_ingest_filename(filename)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    if not data:
        raise HTTPException(400, "empty file")

    aid = agent_id.strip()
    s_handle = await agent_server.settings(aid)
    agent_cf = await s_handle.get_all()

    try:
        meta = await rag_service.ingest_bytes(
            agent_id=aid,
            data=data,
            filename=filename,
            mime_type=mime_type,
            source="settings",
            field_id=field_id or None,
            thread_id=None,
            agent_settings=agent_cf,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Same id must be stored in settings as openai/provider id so deletes hit Azure/OpenAI DB row + index.
    file_id = str(meta.get("provider_file_id") or meta.get("openai_file_id") or uuid.uuid4())
    public = meta.get("gcs_uri") or f"{settings.public_base_url}/settings-upload/{file_id}/{filename}"
    return {
        "id": file_id,
        "filename": filename,
        "public_url": public,
        "mime_type": mime_type,
        "size": len(data),
        "provider_file_id": meta.get("provider_file_id"),
        "openai_file_id": meta.get("openai_file_id"),
        "vector_store_id": meta.get("vector_store_id"),
        "backend_store_id": meta.get("backend_store_id"),
    }
