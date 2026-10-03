"""OpenAI STT/TTS with an in-memory cache served by ``GET /audio/{ref_id}``.

Audio is optional: a text-only agent never touches this module, so the OpenAI key is only
required when an audio part arrives or ``reply_mode`` asks for voice.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.config import settings as app_settings
from src.modules.external.openai.client import get_openai_audio_client

audio_store: dict[str, dict] = {}


def stt_model(agent_settings: dict[str, Any]) -> str:
    return (agent_settings.get("stt_model") or "gpt-4o-transcribe").strip()


def _tts_model(agent_settings: dict[str, Any]) -> str:
    return (agent_settings.get("tts_model") or "gpt-4o-mini-tts").strip()


def _tts_voice(agent_settings: dict[str, Any]) -> str:
    return (agent_settings.get("tts_voice") or "alloy").strip()


async def transcribe(*, data: bytes, filename: str | None, mime_type: str | None, agent_settings: dict[str, Any]) -> str:
    client = get_openai_audio_client()
    result = await client.audio.transcriptions.create(
        model=stt_model(agent_settings),
        file=(filename or "audio.webm", data, mime_type or "audio/webm"),
    )
    return (getattr(result, "text", "") or "").strip()


async def generate_speech(text: str, agent_settings: dict[str, Any]) -> tuple[str, str]:
    client = get_openai_audio_client()
    response = await client.audio.speech.create(
        model=_tts_model(agent_settings),
        voice=_tts_voice(agent_settings),
        input=text,
    )
    ref_id = str(uuid.uuid4())
    mime_type = "audio/mpeg"
    audio_store[ref_id] = {"data": response.content, "mime_type": mime_type}
    return f"{app_settings.public_base_url}/audio/{ref_id}", mime_type
