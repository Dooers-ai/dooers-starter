"""Function-tool factory for RAG lookup on the configured pipeline."""

from __future__ import annotations

from typing import Any

from agents import function_tool

from src.modules.rag.knowledge_settings import field_id_to_tool_suffix

_DOOERS_FILE_SEARCH_DESCRIPTION = (
    "Searches the agent knowledge base configured in «Base de Conhecimento». "
    "Use for factual/document-grounded answers (policies, product details, procedures, FAQ). "
    "If no relevant result is found, explicitly say so."
)


def build_dooers_file_search_tool(
    *,
    agent_id: str,
    field_id: str,
    max_num_results: int,
    agent_settings: dict[str, Any] | None = None,
):
    suffix = field_id_to_tool_suffix(field_id)
    tool_name = f"dooers_file_search_{suffix}"
    @function_tool(
        name_override=tool_name,
        description_override=f"{_DOOERS_FILE_SEARCH_DESCRIPTION} Knowledge field id: {field_id}.",
    )
    async def dooers_file_search(query: str) -> str:
        from src.modules.rag.service import rag_service as _rag

        q = (query or "").strip()
        if not q:
            return f"Provide a non-empty query for {tool_name}."
        out = await _rag.search_knowledge_for_field(
            agent_id=agent_id,
            field_id=field_id,
            query=q,
            max_results=max_num_results,
            agent_settings=agent_settings,
        )
        text = out.strip()
        if not text:
            return f"No relevant passages were found for field '{field_id}'."
        return text

    return dooers_file_search
