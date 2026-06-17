"""OpenAI STT/TTS e cache em memória servido por GET /audio/{ref_id}."""

from __future__ import annotations

import uuid
from typing import Any

from src.config import settings as app_settings
from src.modules.external.openai import get_openai_audio_client

# Partilhado com `main.py` (rota de download do áudio gerado).
audio_store: dict[str, dict] = {}


def stt_model(agent_settings: dict[str, Any]) -> str:
    return (
        agent_settings.get("stt_model") or agent_settings.get("llm_speech_model") or "gpt-4o-transcribe"
    ).strip()


def _tts_model(agent_settings: dict[str, Any]) -> str:
    return (agent_settings.get("tts_model") or "tts-1").strip()


def _tts_voice(agent_settings: dict[str, Any]) -> str:
    return (agent_settings.get("tts_voice") or "alloy").strip()


async def generate_speech(text: str, agent_settings: dict[str, Any]) -> tuple[str, str]:
    client = get_openai_audio_client(agent_settings)
    response = await client.audio.speech.create(
        model=_tts_model(agent_settings),
        voice=_tts_voice(agent_settings),
        input=text,
    )
    audio_bytes = response.content
    ref_id = str(uuid.uuid4())
    mime_type = "audio/mpeg"
    audio_store[ref_id] = {"data": audio_bytes, "mime_type": mime_type}
    url = f"{app_settings.service_url.rstrip('/')}{app_settings.api_prefix}/audio/{ref_id}"
    return url, mime_type
