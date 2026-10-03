"""Managed Dooers RAG configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from src.config import settings


def managed_rag_configured() -> bool:
    return settings.resolved_rag_pipeline == "dooers" and bool(settings.dooers_rag_service_url.strip())


def require_managed_rag() -> str:
    if not managed_rag_configured():
        raise RuntimeError(
            "Managed Dooers RAG is not configured (DOOERS_RAG_SERVICE_URL). "
            "`dooers push` injects it when the organization has the RAG feature."
        )
    return settings.dooers_rag_service_url.strip().rstrip("/")


def resolve_upload_strategy(filename: str) -> Literal["auto", "structured", "document"]:
    """Spreadsheets become one entity per row; prose becomes chunks."""
    ext = Path(filename or "").suffix.lower()
    if ext in {".csv", ".xlsx", ".xls", ".json"}:
        return "structured"
    if ext in {".pdf", ".docx", ".txt", ".md", ".html"}:
        return "document"
    return "auto"
