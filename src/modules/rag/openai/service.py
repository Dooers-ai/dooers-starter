"""OpenAI RAG implementation: vector stores + optional GCS archive."""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from typing import Any

from src.modules.external.openai.rag_client import get_openai_rag_client
from src.modules.rag.archive_storage import delete_archive_uri, upload_archive_bytes
from src.modules.rag.knowledge_repository import knowledge_repository
from src.modules.rag.knowledge_settings import normalize_knowledge_field_id

logger = logging.getLogger(__name__)

class OpenAIRagService:
    async def get_or_create_vector_store_id(
        self,
        agent_id: str,
        *,
        field_id: str | None,
        source: str,
        agent_settings: dict[str, Any] | None = None,
    ) -> str:
        _ = agent_settings
        scope_field_id = normalize_knowledge_field_id(field_id, source=source)
        existing = await knowledge_repository.get_backend_store_id(agent_id, field_id=scope_field_id)
        if existing:
            return existing

        client = get_openai_rag_client()
        name = f"{agent_id}__{scope_field_id}"
        stores = client.vector_stores.list()
        vs_id: str | None = None
        for s in stores.data:
            if s.name == name:
                vs_id = s.id
                break
        if vs_id is None:
            created = client.vector_stores.create(name=name)
            vs_id = created.id
            logger.info("Created OpenAI vector store %s for agent %s", vs_id, agent_id)

        await knowledge_repository.upsert_vector_store(agent_id, vs_id, field_id=scope_field_id)
        return vs_id

    async def ingest_bytes(
        self,
        *,
        agent_id: str,
        data: bytes,
        filename: str,
        mime_type: str | None,
        source: str,
        field_id: str | None = None,
        thread_id: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = agent_settings
        scope_field_id = normalize_knowledge_field_id(field_id, source=source)
        artifact_ref = str(uuid.uuid4())
        archive_uri = upload_archive_bytes(
            data,
            agent_id=agent_id,
            field_id=scope_field_id,
            artifact_ref=artifact_ref,
            filename=filename,
            content_type=mime_type,
        )
        vs_id = await self.get_or_create_vector_store_id(
            agent_id,
            field_id=scope_field_id,
            source=source,
            agent_settings=agent_settings,
        )
        client = get_openai_rag_client()
        buf = io.BytesIO(data)
        up = client.files.create(file=(filename, buf), purpose="assistants")
        client.vector_stores.files.create(vector_store_id=vs_id, file_id=up.id)

        await knowledge_repository.insert_knowledge_asset(
            agent_id=agent_id,
            source=source,
            field_id=scope_field_id,
            thread_id=thread_id,
            filename=filename,
            gcs_uri=archive_uri,
            provider_file_id=up.id,
            backend_store_id=vs_id,
        )
        return {
            "backend": "openai",
            "vector_store_id": vs_id,
            "backend_store_id": vs_id,
            "provider_file_id": up.id,
            "openai_file_id": up.id,
            "gcs_uri": archive_uri,
            "filename": filename,
        }

    async def search_knowledge(
        self,
        *,
        agent_id: str,
        query: str,
        max_results: int = 8,
        field_id: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> str:
        _ = agent_settings
        scope_field_id = normalize_knowledge_field_id(field_id, source="settings")
        vs_id = await self.fetch_backend_store_id(agent_id, field_id=scope_field_id)
        if not vs_id:
            return ""
        return await asyncio.to_thread(self._sync_search, vs_id, query, max_results)

    @staticmethod
    def _sync_search(vs_id: str, query: str, max_results: int) -> str:
        client = get_openai_rag_client()
        try:
            page = client.vector_stores.search(
                vector_store_id=vs_id,
                query=query,
                max_num_results=max_results,
            )
        except Exception as e:
            logger.warning("OpenAI vector_stores.search failed: %s", e)
            return ""
        parts: list[str] = []
        for item in getattr(page, "data", None) or []:
            chunk_parts: list[str] = []
            for block in getattr(item, "content", None) or []:
                t = getattr(block, "text", None)
                if t:
                    chunk_parts.append(t)
            parts.append("\n".join(chunk_parts) if chunk_parts else str(item))
        return "\n\n---\n\n".join(parts[:max_results]) if parts else ""

    async def fetch_backend_store_id(self, agent_id: str, *, field_id: str | None = None) -> str | None:
        scope_field_id = normalize_knowledge_field_id(field_id, source="settings")
        return await knowledge_repository.get_backend_store_id(agent_id, field_id=scope_field_id)

    async def delete_ingested_file(
        self,
        *,
        agent_id: str,
        provider_file_id: str,
        backend_store_id: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> None:
        _ = agent_settings
        row = await knowledge_repository.get_by_provider_file_id(agent_id, provider_file_id)
        store_id = (row or {}).get("vector_store_id") or backend_store_id
        gcs_uri = (row or {}).get("gcs_uri")
        client = get_openai_rag_client()
        if store_id:
            try:
                client.vector_stores.files.delete(vector_store_id=str(store_id), file_id=provider_file_id)
            except Exception as e:
                logger.warning("OpenAI vector store detach failed (agent=%s file=%s): %s", agent_id, provider_file_id, e)
        try:
            client.files.delete(provider_file_id)
        except Exception as e:
            logger.warning("OpenAI file delete failed (agent=%s file=%s): %s", agent_id, provider_file_id, e)
        delete_archive_uri(gcs_uri)
        await knowledge_repository.delete_by_provider_file_id(agent_id, provider_file_id)


openai_rag_service = OpenAIRagService()
