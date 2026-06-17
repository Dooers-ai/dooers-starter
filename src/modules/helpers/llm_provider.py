"""OpenAI Agents SDK model routing: OpenAI / Azure chat clients vs LiteLLM for Gemini / Claude."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from agents import RunConfig
from agents.model_settings import ModelSettings
from agents.models.multi_provider import MultiProvider
from openai import AsyncOpenAI

from src.modules.llm.factory import (
    USER_MESSAGE_MISSING_AZURE_ENDPOINT,
    USER_MESSAGE_UNKNOWN_LLM_PROVIDER,
    UserVisibleAgentError,
    _resolve_chat_provider_and_model,
    _strip,
    ensure_llm_provider_config,
    provider_api_key,
)


class LiteLLMAPIKeyUnset(UserVisibleAgentError):
    """Litellm keys are propagated via OS env vars for the Agents LiteLLM provider."""


def resolve_agents_run_model_name(agent_settings: dict[str, Any]) -> tuple[str, str, str]:
    """Return `(provider_key, logical_model_name, agents_model_identifier)`.

    `agents_model_identifier` is passed to Agents as the model name (possibly `litellm/...`).
    """
    ensure_llm_provider_config(agent_settings)
    provider, model = _resolve_chat_provider_and_model(agent_settings)

    if provider == "openai":
        return provider, model, model
    if provider == "azure_openai":
        return provider, model, model

    if provider == "gemini":
        litellm_id = model if model.startswith("gemini/") else f"gemini/{model}"
        return provider, model, f"litellm/{litellm_id}"

    if provider == "claude":
        litellm_id = model if model.startswith("anthropic/") else f"anthropic/{model}"
        return provider, model, f"litellm/{litellm_id}"

    raise UserVisibleAgentError(USER_MESSAGE_UNKNOWN_LLM_PROVIDER)


def build_model_provider(agent_settings: dict[str, Any]) -> MultiProvider:
    ensure_llm_provider_config(agent_settings)
    key = provider_api_key(agent_settings)
    provider, _model = _resolve_chat_provider_and_model(agent_settings)

    if provider == "azure_openai":
        try:
            from openai import AsyncAzureOpenAI
        except ImportError as e:  # pragma: no cover
            raise UserVisibleAgentError(USER_MESSAGE_UNKNOWN_LLM_PROVIDER) from e

        endpoint = _strip(agent_settings.get("provider_azure_openai_endpoint"))
        if not endpoint:
            raise UserVisibleAgentError(USER_MESSAGE_MISSING_AZURE_ENDPOINT)
        api_version = _strip(agent_settings.get("provider_azure_openai_api_version")) or "2024-08-01-preview"
        client = AsyncAzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=key,
        )
        return MultiProvider(openai_client=client)

    if provider == "openai":
        client = AsyncOpenAI(api_key=key)
        return MultiProvider(openai_client=client)

    return MultiProvider()


def build_agents_run_config(agent_settings: dict[str, Any], *, agents_model_identifier: str) -> RunConfig:
    return RunConfig(
        model=agents_model_identifier,
        model_provider=build_model_provider(agent_settings),
        model_settings=ModelSettings(temperature=0.2),
    )


def _snapshot_env(names: tuple[str, ...]) -> dict[str, str | None]:
    return {n: os.environ.get(n) for n in names}


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, val in snapshot.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@asynccontextmanager
async def litellm_api_key_env(agent_settings: dict[str, Any]):
    """LiteLLM inside `openai-agents` expects provider keys via environment variables."""
    provider, _logical, agents_model_id = resolve_agents_run_model_name(agent_settings)
    if not agents_model_id.startswith("litellm/"):
        yield
        return

    key = provider_api_key(agent_settings)
    if not key.strip():
        raise LiteLLMAPIKeyUnset(
            "A chave de API do LLM deve estar configurada para este fornecedor (LiteLLM)."
        )

    if provider == "gemini":
        names = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
        snap = _snapshot_env(names)
        os.environ["GEMINI_API_KEY"] = key
        os.environ["GOOGLE_API_KEY"] = key
        try:
            yield
        finally:
            _restore_env(snap)
    elif provider == "claude":
        names = ("ANTHROPIC_API_KEY",)
        snap = _snapshot_env(names)
        os.environ["ANTHROPIC_API_KEY"] = key
        try:
            yield
        finally:
            _restore_env(snap)
    else:
        yield
