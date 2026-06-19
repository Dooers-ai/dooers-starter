"""Async Supabase client — shared singleton keyed by (url, key) for multi-config support."""

from __future__ import annotations

from typing import Any

from supabase import AsyncClient, acreate_client

from src.config import settings as _app_settings

_clients: dict[tuple[str, str], AsyncClient] = {}


def _resolve_credentials(agent_settings: dict[str, Any] | None) -> tuple[str, str]:
    """Return (url, key), preferring agent_settings over env vars."""
    s = agent_settings or {}
    url = (s.get("supabase_url") or _app_settings.supabase_url or "").strip()
    key = (s.get("supabase_key") or _app_settings.supabase_key or "").strip()
    return url, key


async def get_supabase_client_for_settings(
    agent_settings: dict[str, Any] | None = None,
) -> AsyncClient:
    """Return a cached async Supabase client for the given credentials.

    Priority: agent_settings fields → SUPABASE_URL / SUPABASE_KEY env vars.
    Raises RuntimeError if neither source provides credentials.
    """
    url, key = _resolve_credentials(agent_settings)

    if not url:
        raise RuntimeError(
            "supabase_url not configured. Set it in the agent settings (Banco de Dados) "
            "or the SUPABASE_URL environment variable."
        )
    if not key:
        raise RuntimeError(
            "supabase_key not configured. Set it in the agent settings (Banco de Dados) "
            "or the SUPABASE_KEY environment variable."
        )

    cache_key = (url, key)
    if cache_key not in _clients:
        _clients[cache_key] = await acreate_client(url, key)
    return _clients[cache_key]


async def get_supabase_client() -> AsyncClient:
    """Convenience wrapper: env-var-only credentials (used by webhook handlers)."""
    return await get_supabase_client_for_settings(None)
