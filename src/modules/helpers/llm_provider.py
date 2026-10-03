"""OpenAI Agents SDK wiring for the Dooers Gateway (or BYO OpenAI).

The gateway speaks Chat Completions. The Agents SDK defaults to the Responses API, so we build a
``MultiProvider`` with ``openai_use_responses=False`` and read thread history in the matching
``openai_completions`` wire format — mixing the two formats is the most common silent failure.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from agents import RunConfig
from agents.model_settings import ModelSettings
from agents.models.multi_provider import MultiProvider
from openai import AsyncOpenAI
from openai.types.shared.reasoning import Reasoning

from src.config import settings
from src.modules.llm.factory import ensure_llm_provider_config, normalize_llm_provider, resolve_chat_model
from src.modules.llm.gateway_models import allowed_model_ids

_ALLOWED_REASONING_EFFORT = frozenset({"none", "low", "medium", "high"})
# Model families that reject ``temperature`` and take a reasoning effort instead.
_REASONING_FAMILIES = ("gpt-5", "o1", "o3", "o4", "claude-opus-5", "glm-5", "gemini-3")


@lru_cache(maxsize=4)
def _client(api_key: str, base_url: str | None) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


def get_chat_client() -> AsyncOpenAI:
    """OpenAI-compatible client for chat turns: gateway when configured, else BYO OpenAI."""
    ensure_llm_provider_config({})
    if normalize_llm_provider() == "dooers_gateway":
        return _client(settings.dooers_gateway_api_key.strip(), settings.gateway_base_url)
    return _client(settings.openai_api_key.strip(), None)


def resolve_agents_wire_format() -> str:
    """History/input format for ``memory.get_history`` and ``format_user_input``."""
    return "openai_completions" if normalize_llm_provider() == "dooers_gateway" else "openai_responses"


def resolve_agents_run_model_name(agent_settings: dict[str, Any]) -> str:
    ensure_llm_provider_config(agent_settings)
    return resolve_chat_model(agent_settings, allowed=allowed_model_ids() or None)


def build_model_provider() -> MultiProvider:
    return MultiProvider(
        openai_client=get_chat_client(),
        openai_use_responses=normalize_llm_provider() != "dooers_gateway",
    )


def _is_reasoning_model(model: str) -> bool:
    normalized = (model or "").strip().lower()
    return normalized.startswith(_REASONING_FAMILIES)


def build_agents_run_config(
    agent_settings: dict[str, Any],
    *,
    model: str,
    prompt_cache_key: str | None = None,
) -> RunConfig:
    kwargs: dict[str, Any] = {}
    if _is_reasoning_model(model):
        effort = str(agent_settings.get("reasoning_effort") or "").strip().lower()
        if effort in _ALLOWED_REASONING_EFFORT:
            kwargs["reasoning"] = Reasoning(effort=effort)  # type: ignore[arg-type]
    else:
        kwargs["temperature"] = 0.2
    if prompt_cache_key:
        kwargs["extra_args"] = {"prompt_cache_key": prompt_cache_key}
    return RunConfig(
        model=model,
        model_provider=build_model_provider(),
        model_settings=ModelSettings(**kwargs),
    )
