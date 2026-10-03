"""Filename rules for knowledge-base uploads."""

from __future__ import annotations

import os

from fastapi import HTTPException

RAG_INGEST_ALLOWED_EXTENSIONS = frozenset({".pdf", ".csv", ".xlsx", ".xls", ".docx", ".json", ".txt", ".md"})
RAG_INGEST_ACCEPT = ",".join(sorted(RAG_INGEST_ALLOWED_EXTENSIONS))


def validate_rag_ingest_filename(filename: str) -> None:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in RAG_INGEST_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não permitido para a base de conhecimento. Permitidos: {RAG_INGEST_ACCEPT}",
        )
