"""Resolve RAG pipeline and Azure AI Search credentials: agent settings override env."""

from __future__ import annotations

from typing import Any

from src.config import settings


def _strip(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


def resolve_rag_pipeline(agent_settings: dict[str, Any] | None) -> str:
    if agent_settings:
        p = _strip(agent_settings.get("rag_pipeline")).lower()
        if p in {"openai", "azure_ai_search"}:
            return p
    return (settings.rag_pipeline or "openai").strip().lower()


def resolve_ai_search_endpoint(agent_settings: dict[str, Any] | None) -> str:
    if agent_settings:
        v = _strip(agent_settings.get("rag_azure_ai_search_endpoint"))
        if v:
            return v
    return (settings.azure_ai_search_endpoint or "").strip()


def resolve_ai_search_api_key(agent_settings: dict[str, Any] | None) -> str:
    if agent_settings:
        v = _strip(agent_settings.get("rag_azure_ai_search_api_key"))
        if v:
            return v
    return (settings.azure_ai_search_api_key or "").strip()


def azure_ai_search_configured(agent_settings: dict[str, Any] | None) -> bool:
    return bool(resolve_ai_search_endpoint(agent_settings) and resolve_ai_search_api_key(agent_settings))
