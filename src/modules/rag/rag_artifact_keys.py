"""Deterministic object keys for RAG source archives (settings / chat ingestion)."""

from __future__ import annotations

import re

RAG_ARTIFACT_PREFIX = "rag-artifacts/v1"
_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_filename(name: str) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1]
    return base.replace("/", "_") or "file"


def safe_segment(seg: str, *, max_len: int = 200) -> str:
    s = (seg or "").strip()
    cleaned = _SAFE.sub("-", s)[:max_len]
    return cleaned or "unknown"


def build_rag_artifact_object_key(
    *,
    agent_id: str,
    field_id: str,
    artifact_ref: str,
    filename: str,
) -> str:
    """
    Mirrors chat-artifacts layout with field scope instead of thread:

        rag-artifacts/v1/{agent_id}/{field_segment}/{artifact_ref}/{filename}
    """
    agent = safe_segment(agent_id.strip() or "unknown-agent") or "unknown-agent"
    field_seg = safe_segment(field_id.strip() or "field") or "field"
    ref = safe_segment((artifact_ref or "").strip() or "unknown-ref") or "unknown-ref"
    return f"{RAG_ARTIFACT_PREFIX}/{agent}/{field_seg}/{ref}/{safe_filename(filename)}"
