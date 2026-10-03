"""Which LLM serves this turn, and the user-facing message when it cannot.

Order of precedence for the chat model:

1. ``llm_model`` set for this turn by the Studio chat picker (``apply_chat_llm_override``);
2. ``llm_models`` — the creator's default in Studio (options come from the gateway allow-list);
3. ``DEFAULT_LLM_MODEL`` when the key allows it, else the first allow-listed model.

Provider: the Dooers Gateway whenever ``DOOERS_GATEWAY_API_KEY`` is set; a BYO ``OPENAI_API_KEY``
otherwise. Audio (STT/TTS) is always vendor-direct OpenAI because the gateway serves text models.
"""

from __future__ import annotations

from typing import Any, Literal

from src.config import settings

ProviderKey = Literal["dooers_gateway", "openai"]


class UserVisibleAgentError(ValueError):
    """An error whose message is safe and useful to show to the end user."""


USER_MESSAGE_MISSING_LLM = (
    "Nenhum modelo de linguagem está configurado para este agente. "
    "Defina DOOERS_GATEWAY_API_KEY no ambiente (ou OPENAI_API_KEY como alternativa)."
)
USER_MESSAGE_MISSING_AUDIO = (
    "Áudio (transcrição e voz) requer OPENAI_API_KEY no ambiente do agente. "
    "Envie a mensagem em texto ou peça ao criador do agente para configurar a chave."
)
USER_MESSAGE_MODEL_NOT_ALLOWED = "O modelo selecionado não está disponível para a chave de API deste agente. Escolha outro modelo na lista."


def _strip(value: Any) -> str:
    return (str(value) if value is not None else "").strip()


def normalize_llm_provider(agent_settings: dict[str, Any] | None = None) -> ProviderKey:
    _ = agent_settings
    return "dooers_gateway" if settings.uses_dooers_gateway else "openai"


def resolve_chat_model(agent_settings: dict[str, Any], *, allowed: tuple[str, ...] | None = None) -> str:
    """Model id for this turn. ``allowed`` (gateway allow-list) wins over any configured value."""
    requested = _strip(agent_settings.get("llm_model")) or _strip(agent_settings.get("llm_models"))
    # Legacy ``provider:model`` values from older starters: keep the model part.
    if ":" in requested:
        requested = requested.split(":", 1)[1].strip()
    if allowed:
        if requested and requested in allowed:
            return requested
        if settings.default_llm_model in allowed:
            return settings.default_llm_model
        return allowed[0]
    return requested or settings.default_llm_model


def ensure_llm_provider_config(agent_settings: dict[str, Any]) -> None:
    if not settings.uses_dooers_gateway and not settings.openai_api_key.strip():
        raise UserVisibleAgentError(USER_MESSAGE_MISSING_LLM)


def ensure_audio_config() -> None:
    if not settings.openai_api_key.strip():
        raise UserVisibleAgentError(USER_MESSAGE_MISSING_AUDIO)


def map_llm_api_error(exc: BaseException) -> UserVisibleAgentError | None:
    """Translate gateway/vendor denials into a message the user can act on."""
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()
    if status in {401, 403} or "model_not_allowed" in text or "not allowed" in text:
        return UserVisibleAgentError(USER_MESSAGE_MODEL_NOT_ALLOWED)
    if status == 404 and "model" in text:
        return UserVisibleAgentError(USER_MESSAGE_MODEL_NOT_ALLOWED)
    return None
