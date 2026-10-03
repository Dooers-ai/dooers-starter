"""``AgentConfig.on_settings_updated``: delete RAG sources the creator removed in Studio."""

from __future__ import annotations

import logging
from typing import Any

from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_IDS
from src.modules.rag.knowledge_sync import document_to_settings_file_item, invalidate_knowledge_hydrate_cache
from src.modules.rag.service import rag_service

logger = logging.getLogger(__name__)


def _ids(raw: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            oid = item.get("provider_file_id") or item.get("id")
            if oid:
                out[str(oid)] = item
    return out


async def on_settings_updated(agent_id: str, field_id: str, old_value: Any, new_value: Any) -> None:
    if field_id not in KNOWLEDGE_FIELD_IDS or not rag_service.enabled:
        return
    invalidate_knowledge_hydrate_cache(agent_id)
    retained = set(_ids(new_value))
    candidates = _ids(old_value)
    # Studio may have shown a hydrated list while the settings row was stale: ask the service too.
    try:
        for doc in await rag_service.list_documents(agent_id=agent_id, field_id=field_id):
            item = document_to_settings_file_item(doc)
            if item["id"]:
                candidates.setdefault(item["id"], item)
    except Exception:  # noqa: BLE001
        logger.exception("Could not list RAG documents while purging field=%s agent=%s", field_id, agent_id)
    for oid in candidates:
        if oid in retained:
            continue
        try:
            await rag_service.delete_document(agent_id=agent_id, document_id=oid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG cleanup failed agent=%s doc=%s: %s", agent_id, oid, exc)
