"""Show the live RAG inventory in Studio.

The RAG service is the source of truth for which files exist. Studio reads ``FILE_MULTI`` values
from agent settings, so we overlay those fields with the service inventory whenever settings are
read. Deletions in Studio flow back through ``knowledge_settings_hook``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_IDS
from src.modules.rag.rag_config import managed_rag_configured
from src.modules.rag.service import rag_service

logger = logging.getLogger(__name__)

_HYDRATE_TTL_SECONDS = 8.0
_cache: dict[str, tuple[float, dict[str, list[dict[str, Any]]]]] = {}


def document_to_settings_file_item(doc: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(doc.get("document_id") or doc.get("id") or "").strip()
    filename = str(doc.get("filename") or doc.get("name") or "document").strip() or "document"
    return {
        "id": doc_id,
        "filename": filename,
        "public_url": str(doc.get("download_url") or doc.get("public_url") or "").strip(),
        "mime_type": str(doc.get("content_type") or doc.get("mime_type") or "application/octet-stream"),
        "provider_file_id": doc_id,
        "knowledge_base": str(doc.get("knowledge_base") or "").strip() or None,
        "backend_store_id": "dooers_managed_rag",
        "created_at": doc.get("created_at"),
    }


def invalidate_knowledge_hydrate_cache(agent_id: str | None = None) -> None:
    if agent_id:
        _cache.pop(agent_id.strip(), None)
    else:
        _cache.clear()


async def hydrate_settings_knowledge_fields(agent_id: str, values: dict[str, Any]) -> dict[str, Any]:
    if not managed_rag_configured():
        return values
    aid = (agent_id or "").strip()
    if not aid:
        return values
    now = time.monotonic()
    cached = _cache.get(aid)
    if cached and cached[0] > now:
        overlays = cached[1]
    else:
        try:
            docs = await rag_service.list_documents(agent_id=aid)
        except Exception:  # noqa: BLE001 — Studio must still load
            logger.exception("Managed RAG list failed during settings hydrate agent=%s", aid)
            return values
        overlays = {fid: [] for fid in KNOWLEDGE_FIELD_IDS}
        for doc in docs:
            kb = str(doc.get("knowledge_base") or "").strip()
            if kb in overlays:
                item = document_to_settings_file_item(doc)
                if item["id"]:
                    overlays[kb].append(item)
        _cache[aid] = (now + _HYDRATE_TTL_SECONDS, overlays)
    out = dict(values)
    out.update(overlays)
    return out


def install_settings_knowledge_hydrate(persistence: Any) -> bool:
    """Wrap ``persistence.get_settings`` so every settings snapshot shows the RAG inventory."""
    if not managed_rag_configured():
        return False
    if getattr(persistence, "_dooers_knowledge_hydrate_installed", False):
        return True
    original = persistence.get_settings

    async def get_settings_hydrated(agent_id: str) -> dict[str, Any]:
        values = await original(agent_id)
        if not isinstance(values, dict):
            values = {}
        try:
            return await hydrate_settings_knowledge_fields(agent_id, values)
        except Exception:  # noqa: BLE001
            logger.exception("settings knowledge hydrate failed agent=%s", agent_id)
            return values

    persistence.get_settings = get_settings_hydrated  # type: ignore[method-assign]
    persistence._dooers_knowledge_hydrate_installed = True
    return True
