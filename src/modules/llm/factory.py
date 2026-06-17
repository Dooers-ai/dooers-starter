"""Agent settings validation: LLM provider/model and API keys.

Chat execution uses the OpenAI Agents SDK in ``src.modules.agent.capabilities``.
Áudio STT/TTS: sempre API OpenAI (`openai_api_key`).
"""

from __future__ import annotations

from typing import Any


class UserVisibleAgentError(ValueError):
    """Erro com mensagem pensada para o utilizador final (configuração, etc.)."""


def _strip(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


USER_MESSAGE_MISSING_LLM_API_KEY = (
    "As chaves de API do fornecedor de LLM não foram configuradas. "
    "Peça ao criador do agente ou a um administrador da sua organização para configurar as chaves de API nas definições do agente."
)

USER_MESSAGE_MISSING_AZURE_ENDPOINT = (
    "Para Azure, o endpoint não foi configurado. "
    "Peça ao criador do agente ou a um administrador da sua organização para configurar o endpoint nas definições do agente."
)

USER_MESSAGE_MISSING_OPENAI_AUDIO_KEY = (
    "A chave API OpenAI para áudio (STT/TTS) não foi configurada. "
    "Peça ao criador do agente ou a um administrador da sua organização para configurar a chave API OpenAI nas definições do agente."
)

USER_MESSAGE_UNKNOWN_LLM_PROVIDER = (
    "O modelo LLM nas definições não é reconhecido ou não está na lista suportada. "
    "Peça ao criador do agente ou a um administrador da sua organização para escolher um modelo multimodal na lista «Modelo LLM — chat»."
)


def normalize_llm_provider(agent_settings: dict[str, Any]) -> str:
    """Deriva o fornecedor do valor `fornecedor:modelo` em `llm_model`, ou do legado `llm_provider`."""
    raw_model = _strip(agent_settings.get("llm_model"))
    if ":" in raw_model:
        p = raw_model.split(":", 1)[0].strip().lower()
        if p in ("openai", "azure_openai", "gemini", "claude"):
            return p
    raw = agent_settings.get("llm_provider")
    p = _strip(raw if raw is not None else "openai").lower()
    return p if p else "openai"


def _resolve_chat_provider_and_model(agent_settings: dict[str, Any]) -> tuple[str, str]:
    raw = _strip(agent_settings.get("model_processing") or agent_settings.get("llm_model"))
    if ":" in raw:
        provider, model = raw.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if provider in ("openai", "azure_openai", "gemini", "claude") and model:
            return provider, model
        raise UserVisibleAgentError(USER_MESSAGE_UNKNOWN_LLM_PROVIDER)
    provider = normalize_llm_provider(agent_settings)
    model = raw or "gpt-4o-mini"
    return provider, model


def provider_api_key(agent_settings: dict[str, Any]) -> str:
    return _strip(agent_settings.get("provider_api_key"))


def ensure_llm_provider_config(agent_settings: dict[str, Any]) -> None:
    """Garante chave (e endpoint Azure se aplicável). Levanta UserVisibleAgentError se faltar algo."""
    if not provider_api_key(agent_settings):
        raise UserVisibleAgentError(USER_MESSAGE_MISSING_LLM_API_KEY)
    prov, _model = _resolve_chat_provider_and_model(agent_settings)
    if prov == "azure_openai":
        if not _strip(agent_settings.get("provider_azure_openai_endpoint")):
            raise UserVisibleAgentError(USER_MESSAGE_MISSING_AZURE_ENDPOINT)


def openai_api_key_audio(agent_settings: dict[str, Any]) -> str:
    """Chave dedicada à API OpenAI para STT/TTS (sempre OpenAI, independente do chat)."""
    return _strip(agent_settings.get("openai_api_key"))


def ensure_openai_audio_config(agent_settings: dict[str, Any]) -> None:
    """STT/TTS usam sempre a API OpenAI — chave obrigatória."""
    if not openai_api_key_audio(agent_settings):
        raise UserVisibleAgentError(USER_MESSAGE_MISSING_OPENAI_AUDIO_KEY)


def openai_key_for_stt_tts(agent_settings: dict[str, Any]) -> str:
    """Chave OpenAI só para áudio (`openai_api_key`)."""
    ensure_openai_audio_config(agent_settings)
    return openai_api_key_audio(agent_settings)
