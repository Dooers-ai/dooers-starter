"""Keep the Studio model picker equal to what the gateway key may actually use.

``GET {gateway}/v1/models`` returns the allow-list of the key, not the whole catalog. We cache it
for a few minutes, patch the ``llm_models`` SELECT options in the live schema and expose the
tuple so ``resolve_chat_model`` never picks a model the gateway would reject.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from dooers.agents.server.features.settings.models import SettingsFieldType, SettingsSelectOption

from src.config import settings

logger = logging.getLogger(__name__)

LLM_MODELS_FIELD_ID = "llm_models"
CACHE_TTL_SECONDS = 15 * 60.0
_FETCH_TIMEOUT_SECONDS = 10.0

_cache_at = 0.0
_cache: tuple[tuple[str, str], ...] | None = None
_refresh_lock = asyncio.Lock()


def _label(model_id: str, owned_by: str) -> str:
    provider = (owned_by or "").strip().lower() or "dooers"
    return f"{model_id} · {provider}"


def cache_is_stale() -> bool:
    return _cache is None or (time.monotonic() - _cache_at) >= CACHE_TTL_SECONDS


def cached_model_options() -> tuple[tuple[str, str], ...]:
    if _cache:
        return _cache
    return ((settings.default_llm_model, _label(settings.default_llm_model, "dooers")),)


def allowed_model_ids() -> tuple[str, ...]:
    """Model ids the gateway key allows (from cache). Empty when not using the gateway."""
    if not settings.uses_dooers_gateway:
        return ()
    return tuple(model_id for model_id, _ in cached_model_options()) if _cache else ()


async def _fetch() -> tuple[tuple[str, str], ...] | None:
    if not settings.uses_dooers_gateway:
        return None
    url = f"{settings.gateway_base_url}/models"
    headers = {"Authorization": f"Bearer {settings.dooers_gateway_api_key.strip()}"}
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload: Any = response.json()
    except Exception as exc:  # noqa: BLE001 — degrade to cache, never fail the turn
        logger.warning("Gateway /models failed (%s); keeping cached allow-list", type(exc).__name__)
        return None
    rows = payload.get("data") if isinstance(payload, dict) else payload
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id") or "").strip()
        if model_id and model_id not in seen:
            seen.add(model_id)
            options.append((model_id, _label(model_id, str(row.get("owned_by") or ""))))
    if not options:
        logger.warning("Gateway /models returned an empty allow-list")
        return None
    return tuple(options)


async def fetch_gateway_model_options(*, force: bool = False) -> tuple[tuple[str, str], ...]:
    global _cache, _cache_at
    if not settings.uses_dooers_gateway:
        return cached_model_options()
    if not force and not cache_is_stale():
        return cached_model_options()
    fetched = await _fetch()
    if fetched:
        _cache, _cache_at = fetched, time.monotonic()
        logger.info("Gateway model allow-list refreshed (%d models)", len(fetched))
    return cached_model_options()


def apply_model_options_to_schema(schema: Any, options: tuple[tuple[str, str], ...]) -> None:
    if schema is None or not options:
        return
    field = schema.get_field(LLM_MODELS_FIELD_ID)
    if field is None or field.type != SettingsFieldType.SELECT:
        return
    field.options = [SettingsSelectOption(value=value, label=label) for value, label in options]
    ids = {value for value, _ in options}
    field.value = settings.default_llm_model if settings.default_llm_model in ids else options[0][0]


async def refresh_schema_llm_models(schema: Any, *, force: bool = False) -> tuple[tuple[str, str], ...]:
    options = await fetch_gateway_model_options(force=force)
    apply_model_options_to_schema(schema, options)
    return options


async def maybe_refresh_schema_llm_models_background(schema: Any) -> None:
    """Refresh a stale cache without blocking the turn; skip if another refresh is running."""
    if not settings.uses_dooers_gateway or not cache_is_stale() or _refresh_lock.locked():
        return
    async with _refresh_lock:
        if cache_is_stale():
            await refresh_schema_llm_models(schema, force=True)
