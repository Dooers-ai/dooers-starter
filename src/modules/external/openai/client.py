"""Vendor-direct OpenAI client for audio (STT/TTS). Chat goes through the gateway — see helpers/llm_provider."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI
from src.config import settings
from src.modules.llm.factory import ensure_audio_config


@lru_cache(maxsize=1)
def _client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key)


def get_openai_audio_client() -> AsyncOpenAI:
    ensure_audio_config()
    return _client(settings.openai_api_key.strip())
