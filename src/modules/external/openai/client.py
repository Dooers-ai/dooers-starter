"""Cliente AsyncOpenAI para áudio (STT/TTS) com chave das settings do agente."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from src.modules.llm.factory import openai_key_for_stt_tts


def get_openai_audio_client(agent_settings: dict[str, Any]) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=openai_key_for_stt_tts(agent_settings))
