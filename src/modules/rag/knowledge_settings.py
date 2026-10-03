"""Knowledge-base fields in agent settings.

Each ``FILE_MULTI`` field listed here is one knowledge base in the managed RAG service, named
after the field id. Add a field id to ``KNOWLEDGE_FIELD_IDS`` and a matching ``SettingsField`` in
``schemas.py`` to give the agent a second, separately searchable base (e.g. ``policies``,
``catalog``).
"""

from __future__ import annotations

from typing import Any

KNOWLEDGE_FIELD_ID = "knowledge"
KNOWLEDGE_FIELD_IDS: tuple[str, ...] = (KNOWLEDGE_FIELD_ID,)


def knowledge_field_ids_with_files(values: dict[str, Any]) -> list[str]:
    return [fid for fid in KNOWLEDGE_FIELD_IDS if isinstance(values.get(fid), list) and values.get(fid)]


def agent_settings_have_knowledge_files(values: dict[str, Any]) -> bool:
    return bool(knowledge_field_ids_with_files(values))
