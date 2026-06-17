"""Provider-routed RAG service (openai | azure_ai_search)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agents import FileSearchTool

from src.modules.helpers.llm_provider import resolve_agents_run_model_name
from src.modules.rag.azure.service import azure_rag_service
from src.modules.rag.knowledge_repository import knowledge_repository
from src.modules.rag.knowledge_settings import knowledge_field_ids_with_files
from src.modules.rag.openai.service import openai_rag_service
from src.modules.rag.rag_config import azure_ai_search_configured, resolve_rag_pipeline
from src.modules.tools.rag.dooers_file_search_tool import build_dooers_file_search_tool


def resolve_rag_max_num_results(agent_settings: dict[str, Any]) -> int:
    raw_max = agent_settings.get("rag_max_num_results") or agent_settings.get(
        "file_search_max_num_results",
    )
    try:
        return max(1, min(50, int(raw_max))) if raw_max is not None and str(raw_max).strip() else 5
    except (TypeError, ValueError):
        return 5


class ResolvedKnowledgeField:
    """Population + backend id for one settings knowledge field."""

    __slots__ = ("field_id", "backend_store_id")

    def __init__(self, *, field_id: str, backend_store_id: str | None) -> None:
        self.field_id = field_id
        self.backend_store_id = backend_store_id


class RagService:
    def pipeline(self, agent_settings: dict[str, Any] | None = None) -> str:
        return resolve_rag_pipeline(agent_settings)

    def _impl(self, agent_settings: dict[str, Any] | None):
        return azure_rag_service if self.pipeline(agent_settings) == "azure_ai_search" else openai_rag_service

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
        if self.pipeline(agent_settings) == "azure_ai_search" and not azure_ai_search_configured(agent_settings):
            raise ValueError(
                "RAG backend is Azure AI Search but endpoint and admin key are missing "
                "(agent settings «Documentos (RAG)» or AZURE_AI_SEARCH_ENDPOINT / AZURE_AI_SEARCH_API_KEY)."
            )
        return await self._impl(agent_settings).ingest_bytes(
            agent_id=agent_id,
            data=data,
            filename=filename,
            mime_type=mime_type,
            source=source,
            field_id=field_id,
            thread_id=thread_id,
            agent_settings=agent_settings,
        )

    async def search_knowledge(self, *, agent_id: str, query: str, max_results: int = 8) -> str:
        return await self._impl(None).search_knowledge(
            agent_id=agent_id,
            query=query,
            max_results=max_results,
            field_id=None,
            agent_settings=None,
        )

    async def search_knowledge_for_field(
        self,
        *,
        agent_id: str,
        field_id: str,
        query: str,
        max_results: int = 8,
        agent_settings: dict[str, Any] | None = None,
    ) -> str:
        return await self._impl(agent_settings).search_knowledge(
            agent_id=agent_id,
            field_id=field_id,
            query=query,
            max_results=max_results,
            agent_settings=agent_settings,
        )

    async def fetch_backend_store_id(self, agent_id: str, agent_settings: dict[str, Any] | None = None) -> str | None:
        return await self._impl(agent_settings).fetch_backend_store_id(agent_id, field_id=None)

    async def fetch_backend_store_id_for_field(
        self,
        *,
        agent_id: str,
        field_id: str,
        agent_settings: dict[str, Any] | None = None,
    ) -> str | None:
        return await self._impl(agent_settings).fetch_backend_store_id(agent_id, field_id=field_id)

    async def delete_ingested_file(
        self,
        *,
        agent_id: str,
        provider_file_id: str,
        backend_store_id: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> None:
        # Route by stored backend id: OpenAI vector stores are "vs_*"; Azure stores index name slugs.
        row = await knowledge_repository.get_by_provider_file_id(agent_id, provider_file_id)
        merged_store = str((row or {}).get("vector_store_id") or backend_store_id or "").strip()
        if merged_store.startswith("vs_"):
            impl = openai_rag_service
        elif merged_store:
            impl = azure_rag_service
        else:
            impl = self._impl(agent_settings)
        await impl.delete_ingested_file(
            agent_id=agent_id,
            provider_file_id=provider_file_id,
            backend_store_id=merged_store or None,
            agent_settings=agent_settings,
        )

    def requires_native_openai_file_search_support(self, agent_settings: dict[str, Any] | None = None) -> bool:
        """Native FileSearchTool only when Azure OpenAI / OpenAI chat + OpenAI vector pipeline."""
        return self.pipeline(agent_settings) == "openai"

    async def resolve_knowledge_field_backends(
        self,
        *,
        agent_id: str,
        agent_settings: dict[str, Any],
        field_ids_allowlist: Iterable[str] | None,
    ) -> list[ResolvedKnowledgeField]:
        """Settings fields that currently list at least one KB file; optional allowlist intersections order."""
        populated = knowledge_field_ids_with_files(agent_settings)
        if field_ids_allowlist is None:
            ordered = populated
        else:
            allowed = {str(x).strip() for x in field_ids_allowlist if str(x).strip()}
            ordered = [fid for fid in populated if fid in allowed]
        out: list[ResolvedKnowledgeField] = []
        for fid in ordered:
            backend_id = await self.fetch_backend_store_id_for_field(
                agent_id=agent_id,
                field_id=fid,
                agent_settings=agent_settings,
            )
            out.append(ResolvedKnowledgeField(field_id=fid, backend_store_id=backend_id))
        return out

    def assemble_file_search_tooling(
        self,
        *,
        agent_id: str,
        agent_settings: dict[str, Any],
        resolved_fields: list[ResolvedKnowledgeField],
        max_num_results: int | None,
    ) -> tuple[list[Any], str]:
        """Native OpenAI ``FileSearchTool`` when possible; else per-field Dooers function tools."""
        mr = resolve_rag_max_num_results(agent_settings) if max_num_results is None else max_num_results
        if not resolved_fields:
            return [], "dooers_file_search_*"

        ids = [r.field_id for r in resolved_fields]
        provider, _, _ = resolve_agents_run_model_name(agent_settings)
        native_ok = (
            len(ids) == 1
            and self.requires_native_openai_file_search_support(agent_settings)
            and provider in {"openai", "azure_openai"}
        )

        tools: list[Any] = []

        if native_ok:
            store = resolved_fields[0].backend_store_id
            if store:
                tools.append(
                    FileSearchTool(
                        vector_store_ids=[str(store)],
                        max_num_results=mr,
                    )
                )
                return tools, "file_search"

        for row in resolved_fields:
            tools.append(
                build_dooers_file_search_tool(
                    agent_id=agent_id,
                    field_id=row.field_id,
                    max_num_results=mr,
                    agent_settings=agent_settings,
                )
            )
        return tools, "dooers_file_search_<field>"

    async def attach_file_search_tools(
        self,
        *,
        agent_id: str,
        agent_settings: dict[str, Any],
        field_ids_allowlist: Iterable[str] | None = None,
        max_num_results: int | None = None,
    ) -> tuple[list[Any], str]:
        """Resolve populated KB fields (+ store ids) and build OpenAI or Dooers file-search tools."""
        resolved = await self.resolve_knowledge_field_backends(
            agent_id=agent_id,
            agent_settings=agent_settings,
            field_ids_allowlist=field_ids_allowlist,
        )
        return self.assemble_file_search_tooling(
            agent_id=agent_id,
            agent_settings=agent_settings,
            resolved_fields=resolved,
            max_num_results=max_num_results,
        )


rag_service = RagService()
