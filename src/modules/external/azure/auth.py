"""Azure shared credentials for storage/search.

AI Search endpoint/key resolve from agent_settings when passed; env is fallback."""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.modules.rag.rag_config import resolve_ai_search_api_key, resolve_ai_search_endpoint


def get_ai_search_endpoint(agent_settings: dict[str, Any] | None = None) -> str:
    return resolve_ai_search_endpoint(agent_settings)


def get_ai_search_api_key(agent_settings: dict[str, Any] | None = None) -> str:
    return resolve_ai_search_api_key(agent_settings)


def get_storage_connection_string() -> str:
    return (settings.azure_storage_connection_string or "").strip()


def get_storage_container() -> str:
    return (settings.azure_storage_container or "").strip()
