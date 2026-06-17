"""Sync OpenAI client for RAG ingestion/search."""

from __future__ import annotations

from openai import OpenAI

from src.config import settings


def get_openai_rag_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, timeout=120.0)
