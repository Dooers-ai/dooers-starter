"""Knowledge-base field ids in agent settings (`FILE_MULTI` upload lists)."""

from __future__ import annotations

import re
from typing import Any


BASE_DE_CONHECIMENTO_FIELD_ID = "base_de_conhecimento"
"""Preferido: uploads da «Base de Conhecimento» no schema."""

def _non_empty_upload_list(raw: Any) -> bool:
    return isinstance(raw, list) and len(raw) > 0


def agent_settings_have_knowledge_files(values: dict[str, Any]) -> bool:
    """True se há pelo menos um ficheiro listado para qualquer campo de KB."""
    return len(knowledge_field_ids_with_files(values)) > 0


def knowledge_field_ids_with_files(values: dict[str, Any]) -> list[str]:
    """All FILE_MULTI-like settings ids that currently have at least one file entry."""
    out: list[str] = []
    for key, raw in values.items():
        if isinstance(key, str) and _non_empty_upload_list(raw):
            out.append(key)
    return sorted(set(out))


def normalize_knowledge_field_id(field_id: str | None, *, source: str = "settings") -> str:
    """Stable scope id used to isolate backends per knowledge source/field."""
    raw = (field_id or "").strip() or ("chat_uploads" if source in {"chat", "form"} else BASE_DE_CONHECIMENTO_FIELD_ID)
    safe = re.sub(r"[^a-zA-Z0-9_\\-]", "_", raw)
    return safe[:80] or BASE_DE_CONHECIMENTO_FIELD_ID


def field_id_to_tool_suffix(field_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", field_id.strip())
    return safe.lower()[:40] or "kb"
