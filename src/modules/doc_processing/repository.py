"""Where processed documents live between turns.

Extraction happens once, when the attachment arrives. The result is cached in memory and
persisted in the agent database through the SDK façade (``await agent_server.database()``), so
it survives restarts and works with both ``postgres`` and the managed ``dooers`` database.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from dooers.agents.server import AgentMemory

from src.modules.doc_processing.models import ProcessedDocument

logger = logging.getLogger(__name__)

_TABLE = "agent_thread_documents"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    document_id TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    thread_id   TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    status      TEXT NOT NULL,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS {_TABLE}_thread_idx ON {_TABLE} (agent_id, thread_id);
"""

_memory: dict[str, ProcessedDocument] = {}
_schema_ready = False


def derive_document_id(*, agent_id: str, thread_id: str, event_id: str, filename: str) -> str:
    raw = "|".join(part.strip() for part in (agent_id, thread_id, event_id, filename))
    return "doc_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


async def _database():
    from src.modules.agent.agent import agent_server

    return await agent_server.database()


async def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    db = await _database()
    await db.execute(_SCHEMA)
    _schema_ready = True


async def save_processed_document(doc: ProcessedDocument) -> None:
    _memory[doc.document_id] = doc
    try:
        await ensure_schema()
        db = await _database()
        await db.execute(
            f"""
            INSERT INTO {_TABLE} (document_id, agent_id, thread_id, event_id, filename, status, payload)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (document_id) DO UPDATE SET status = EXCLUDED.status, payload = EXCLUDED.payload
            """,
            doc.document_id,
            doc.agent_id,
            doc.thread_id,
            doc.event_id,
            doc.filename,
            doc.status,
            json.dumps(doc.to_dict(), ensure_ascii=False),
        )
    except Exception:  # noqa: BLE001 — in-memory copy still serves this process
        logger.exception("Could not persist processed document %s", doc.document_id)


async def load_processed_document(document_id: str) -> ProcessedDocument | None:
    cached = _memory.get(document_id)
    if cached:
        return cached
    try:
        await ensure_schema()
        db = await _database()
        row = await db.fetchrow(f"SELECT payload FROM {_TABLE} WHERE document_id = $1", document_id)
    except Exception:  # noqa: BLE001
        logger.exception("Could not load processed document %s", document_id)
        return None
    if not row:
        return None
    payload: Any = row.get("payload") if isinstance(row, dict) else row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    doc = ProcessedDocument.from_dict(payload)
    _memory[document_id] = doc
    return doc


def _part_get(part: object, key: str) -> Any:
    return part.get(key) if isinstance(part, dict) else getattr(part, key, None)


async def list_thread_documents(*, memory: AgentMemory, agent_id: str, thread_id: str, limit: int = 120) -> list[ProcessedDocument]:
    """Ready documents attached anywhere in this thread, oldest first."""
    events = await memory.get_history_raw(limit=limit, order="desc")
    out: list[ProcessedDocument] = []
    seen: set[str] = set()
    for event in reversed(events):
        if getattr(event, "type", None) != "message" or not getattr(event, "content", None):
            continue
        for part in event.content:
            if str(_part_get(part, "type") or "") != "document":
                continue
            filename = str(_part_get(part, "filename") or "document")
            doc_id = derive_document_id(agent_id=agent_id, thread_id=thread_id, event_id=event.id, filename=filename)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            doc = await load_processed_document(doc_id)
            if doc and doc.status == "ready":
                out.append(doc)
    return out
