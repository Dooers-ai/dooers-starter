"""Optional file archive storage router for RAG ingestion artifacts."""

from __future__ import annotations

from src.config import settings
from src.modules.external.azure.blob_storage import (
    delete_blob_url,
    upload_bytes_to_blob_name as azure_upload_blob_name,
)
from src.modules.external.gcp.storage import delete_gs_uri, upload_bytes_to_blob_name as gcs_upload_blob_name
from src.modules.rag.rag_artifact_keys import build_rag_artifact_object_key


def resolve_archive_backend() -> str:
    if not settings.store_rag_uploads:
        return "none"
    pref = (settings.rag_storage_service or "none").strip().lower()
    if pref in {"gcp", "azure"}:
        return pref
    return "none"


def upload_archive_bytes(
    data: bytes,
    *,
    agent_id: str,
    field_id: str | None,
    artifact_ref: str,
    filename: str,
    content_type: str | None = None,
) -> str | None:
    """
    Store originals under ``rag-artifacts/v1/{agent}/{field}/{artifact_ref}/{filename}``
    when RAG archival is enabled (GCS or Azure).
    """
    backend = resolve_archive_backend()
    if backend == "none":
        return None
    key = build_rag_artifact_object_key(
        agent_id=agent_id.strip() or "unknown-agent",
        field_id=(field_id or "").strip() or "unknown-field",
        artifact_ref=(artifact_ref or "").strip() or "unknown-ref",
        filename=filename,
    )
    if backend == "gcp":
        return gcs_upload_blob_name(data, key, content_type)
    if backend == "azure":
        return azure_upload_blob_name(data, key, content_type)
    return None


def delete_archive_uri(uri: str | None) -> None:
    if not uri:
        return
    if uri.startswith("gs://"):
        delete_gs_uri(uri)
        return
    if uri.startswith("https://") and ".blob.core.windows.net/" in uri:
        delete_blob_url(uri)
