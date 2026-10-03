"""Thin wrapper over ``dooers.tools.rag`` for handler turns and Studio uploads.

Identity never comes from the model: ``dooers.tools.rag`` binds agent/workspace/user from the
handler turn. HTTP routes (uploads) run outside a turn, so ``bound_rag_context`` recreates that
binding from the ``AgentServer`` persistence.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.modules.rag.rag_config import require_managed_rag, resolve_upload_strategy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def bound_rag_context(agent_id: str) -> AsyncIterator[None]:
    from dooers.tools.rag.runtime import bind_execution_context, current_execution_context
    from dooers.tools.whatsapp.runtime import bind_handler_context, require_persistence, reset_handler_context

    from src.modules.agent.agent import agent_server

    aid = (agent_id or "").strip()
    if not aid:
        raise ValueError("agent_id is required")
    require_managed_rag()

    try:
        require_persistence()
        current = current_execution_context()
        if current is not None and current.agent_id == aid:
            yield
            return
    except Exception:  # noqa: BLE001 — not inside a handler turn
        pass

    await agent_server.ensure_initialized()
    tokens = bind_handler_context(persistence=agent_server.persistence, agent_id=aid)
    bind_execution_context(agent_id=aid, channel="dooers-platform")
    try:
        yield
    finally:
        reset_handler_context(tokens)


def rebind_execution_context(
    *, agent_id: str, organization_id: str = "", workspace_id: str = "", user_id: str = "", channel: str = ""
) -> None:
    """Tools run in child tasks of the handler; the RAG context is per task, so bind it again."""
    from dooers.tools.rag.runtime import bind_execution_context

    bind_execution_context(
        agent_id=agent_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        channel=channel,
    )


def _entity_body(data: dict[str, Any]) -> str:
    if "content" in data and len(data) <= 3:
        return str(data.get("content") or "").strip()
    lines = []
    for key, value in data.items():
        if key.startswith("_") or value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            lines.append(f"{key}: {text}")
    return "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False)


def format_search_hits(hits: list[dict[str, Any]], *, limit: int) -> str:
    """One section per hit with a machine-readable header the model can cite."""
    sections: list[str] = []
    for hit in hits[: max(1, limit)]:
        if not isinstance(hit, dict):
            continue
        data = hit.get("data")
        body = _entity_body(data) if isinstance(data, dict) else str(data or hit.get("text") or hit.get("content") or "")
        body = body.strip()
        if not body:
            continue
        header = f"[knowledge_base={hit.get('knowledge_base') or 'default'}"
        if hit.get("type"):
            header += f" type={hit['type']}"
        score = hit.get("score")
        if isinstance(score, (int, float)):
            header += f" score={float(score):.3f}"
        if hit.get("document_id"):
            header += f" document_id={hit['document_id']}"
        if hit.get("filename") or hit.get("name"):
            header += f" source={hit.get('filename') or hit.get('name')}"
        header += "]"
        sections.append(f"{header}\n{body[:12000]}")
    return "\n\n---\n\n".join(sections)[:60000]


async def search_managed_knowledge(*, query: str, max_results: int = 8, knowledge_bases: list[str] | None = None) -> str:
    from dooers.tools import rag

    require_managed_rag()
    clean = (query or "").strip()
    if not clean:
        return ""
    limit = max(1, min(50, int(max_results or 8)))
    selected = [kb.strip() for kb in (knowledge_bases or []) if str(kb).strip()] or None
    hits = await rag.search(clean, limit=limit, mode="hybrid", knowledge_bases=selected)
    return format_search_hits(hits, limit=limit) if isinstance(hits, list) and hits else ""


async def upload_managed_document(
    *, agent_id: str, data: bytes, filename: str, mime_type: str | None, knowledge_base: str
) -> dict[str, Any]:
    from dooers.tools import rag

    require_managed_rag()
    kb = (knowledge_base or "").strip()
    if not kb:
        raise ValueError("knowledge_base is required")
    async with bound_rag_context(agent_id):
        return await rag.upload(
            name=filename,
            content=data,
            content_type=(mime_type or "application/octet-stream").strip() or "application/octet-stream",
            knowledge_base=kb,
            strategy=resolve_upload_strategy(filename),
            store_original=True,
        )


async def list_managed_documents(*, agent_id: str, knowledge_base: str | None = None) -> list[dict[str, Any]]:
    from dooers.tools import rag

    require_managed_rag()
    async with bound_rag_context(agent_id):
        docs = await rag.list_documents()
    kb = (knowledge_base or "").strip()
    return [
        row
        for row in (docs if isinstance(docs, list) else [])
        if isinstance(row, dict) and (not kb or str(row.get("knowledge_base") or "").strip() == kb)
    ]


async def delete_managed_document(*, agent_id: str, document_id: str) -> None:
    from dooers.tools import rag

    require_managed_rag()
    doc_id = (document_id or "").strip()
    if not doc_id:
        raise ValueError("document_id is required")
    async with bound_rag_context(agent_id):
        await rag.delete(doc_id)
