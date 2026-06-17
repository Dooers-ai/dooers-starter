"""Lifecycle hook: cleanup provider files when KB entries are removed in settings."""

from __future__ import annotations

import logging
from typing import Any

from src.modules.rag.knowledge_repository import knowledge_repository
from src.modules.rag.knowledge_settings import (
    BASE_DE_CONHECIMENTO_FIELD_ID,
)
from src.modules.rag.service import rag_service

logger = logging.getLogger(__name__)

_KNOWLEDGE_FILE_FIELD_IDS = frozenset({BASE_DE_CONHECIMENTO_FIELD_ID})


def _provider_file_ids_in_list(raw: Any) -> set[str]:
    if not isinstance(raw, list):
        return set()
    out: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            oid = item.get("provider_file_id") or item.get("openai_file_id") or item.get("id")
            if oid:
                out.add(str(oid))
    return out


async def _purge_removed_file(agent_id: str, provider_file_id: str, meta: dict[str, Any]) -> None:
    from src.modules.agent.agent import agent_server

    row = await knowledge_repository.get_by_provider_file_id(agent_id, provider_file_id)
    backend_store_id = (row or {}).get("vector_store_id") or meta.get("vector_store_id")
    agent_cf: dict[str, Any] = {}
    try:
        ah = await agent_server.settings(agent_id)
        agent_cf = await ah.get_all()
    except Exception:
        logger.warning("could not load agent settings for rag delete agent_id=%s", agent_id)

    try:
        await rag_service.delete_ingested_file(
            agent_id=agent_id,
            provider_file_id=provider_file_id,
            backend_store_id=str(backend_store_id) if backend_store_id else None,
            agent_settings=agent_cf,
        )
    except Exception as e:
        logger.warning("RAG cleanup failed (agent=%s file=%s): %s", agent_id, provider_file_id, e)


async def on_settings_updated(agent_id: str, field_id: str, old_value: Any, new_value: Any) -> None:
    if field_id not in _KNOWLEDGE_FILE_FIELD_IDS:
        return

    old_list = old_value if isinstance(old_value, list) else []
    new_list = new_value if isinstance(new_value, list) else []
    retained = _provider_file_ids_in_list(new_list)

    for item in old_list:
        if not isinstance(item, dict):
            continue
        oid = item.get("provider_file_id") or item.get("openai_file_id") or item.get("id")
        if not oid:
            continue
        oid = str(oid)
        if oid in retained:
            continue
        await _purge_removed_file(agent_id, oid, item)
