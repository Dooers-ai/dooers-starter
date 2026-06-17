"""Filename rules for uploads that are ingested into RAG (settings, chat, forms)."""

from __future__ import annotations

import os

from fastapi import HTTPException

# Common business document formats for Vector Store ingest.
RAG_INGEST_ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".csv",
        ".xlsx",
        ".xls",
        ".docx",
        ".json",
    }
)

SETTINGS_RAG_ALLOWED_EXTENSIONS = RAG_INGEST_ALLOWED_EXTENSIONS


def validate_rag_ingest_filename(filename: str) -> None:
    """Reject disallowed extensions for any path that calls :func:`rag_service.ingest_bytes`."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in RAG_INGEST_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(RAG_INGEST_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de ficheiro não permitido para memória do agente. Permitidos: {allowed}",
        )


validate_settings_rag_filename = validate_rag_ingest_filename
