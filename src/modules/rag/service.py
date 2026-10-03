"""Knowledge façade used by tools and uploads. Backend: managed Dooers RAG or nothing."""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings
from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_IDS, knowledge_field_ids_with_files
from src.modules.rag.managed import (
    delete_managed_document,
    list_managed_documents,
    search_managed_knowledge,
    upload_managed_document,
)
from src.modules.rag.rag_config import managed_rag_configured

logger = logging.getLogger(__name__)


class RagService:
    @property
    def pipeline(self) -> str:
        return settings.resolved_rag_pipeline

    @property
    def enabled(self) -> bool:
        return managed_rag_configured()

    def knowledge_bases_for(self, agent_settings: dict[str, Any]) -> list[str]:
        """Knowledge bases that currently hold files (one per populated settings field).

        Settings snapshots are hydrated from the RAG inventory (``knowledge_sync``), so an empty
        list here really means "nothing indexed" and the agent is told not to search.
        """
        if not self.enabled:
            return []
        return [fid for fid in knowledge_field_ids_with_files(agent_settings) if fid in KNOWLEDGE_FIELD_IDS]

    async def search(self, *, query: str, knowledge_bases: list[str] | None, max_results: int = 8) -> str:
        if not self.enabled:
            return ""
        return await search_managed_knowledge(query=query, max_results=max_results, knowledge_bases=knowledge_bases)

    async def ingest_bytes(self, *, agent_id: str, data: bytes, filename: str, mime_type: str | None, field_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("Knowledge base is not available: managed Dooers RAG is not configured.")
        return await upload_managed_document(agent_id=agent_id, data=data, filename=filename, mime_type=mime_type, knowledge_base=field_id)

    async def list_documents(self, *, agent_id: str, field_id: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        return await list_managed_documents(agent_id=agent_id, knowledge_base=field_id)

    async def delete_document(self, *, agent_id: str, document_id: str) -> None:
        if not self.enabled:
            return
        await delete_managed_document(agent_id=agent_id, document_id=document_id)


rag_service = RagService()
