"""Azure Blob storage helpers for optional RAG source archive."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlparse

from src.modules.external.azure.auth import get_storage_connection_string, get_storage_container

logger = logging.getLogger(__name__)


def _parse_account_name_key(connection_string: str) -> tuple[str, str] | None:
    """Extract AccountName and AccountKey from an Azure Storage connection string."""
    if not connection_string.strip():
        return None
    name_m = re.search(r"AccountName=([^;]+)", connection_string, re.IGNORECASE)
    key_m = re.search(r"AccountKey=([^;]+)", connection_string, re.IGNORECASE)
    if not name_m or not key_m:
        return None
    return name_m.group(1).strip(), key_m.group(1).strip()


def generate_blob_read_sas_url(blob_name: str, expiration_minutes: int = 60) -> str | None:
    """HTTPS URL with read-only SAS token, or None."""
    conn = get_storage_connection_string()
    container = get_storage_container()
    if not conn or not container or not blob_name.strip():
        return None
    parsed = _parse_account_name_key(conn)
    if not parsed:
        logger.warning("Azure connection string missing AccountName/AccountKey")
        return None
    account_name, account_key = parsed
    try:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("azure-storage-blob not installed")
        return None
    bn = blob_name.strip()
    now = datetime.now(UTC)
    try:
        sas = generate_blob_sas(
            account_name=account_name,
            container_name=container,
            blob_name=bn,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=now + timedelta(minutes=expiration_minutes),
            start=now - timedelta(seconds=60),
        )
    except Exception as e:
        logger.warning("Azure SAS generation failed for %s: %s", bn, e)
        return None
    enc = "/".join(quote(seg, safe="") for seg in bn.split("/"))
    return f"https://{account_name}.blob.core.windows.net/{container}/{enc}?{sas}"


def upload_bytes_to_blob_name(data: bytes, blob_name: str, content_type: str | None = None) -> str | None:
    """Upload to the configured container at ``blob_name``; returns blob HTTPS URL or None."""
    conn = get_storage_connection_string()
    container = get_storage_container()
    if not conn or not container or not blob_name.strip():
        return None
    try:
        from azure.storage.blob import BlobServiceClient  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("azure-storage-blob not installed; skipping blob archive")
        return None
    try:
        client = BlobServiceClient.from_connection_string(conn)
        cont = client.get_container_client(container)
        try:
            cont.create_container()
        except Exception:
            pass
        bn = blob_name.strip()
        blob = cont.get_blob_client(bn)
        blob.upload_blob(
            data,
            overwrite=True,
            content_type=content_type or "application/octet-stream",
        )
        return blob.url
    except Exception as e:
        logger.warning("Azure blob upload failed: %s", e)
        return None


def upload_bytes(data: bytes, filename: str, content_type: str | None = None) -> str | None:
    safe = filename.replace("/", "_") or "file"
    blob_name = f"agent-template/{uuid.uuid4().hex}_{safe}"
    return upload_bytes_to_blob_name(data, blob_name, content_type)


def delete_blob_url(blob_url: str | None) -> None:
    if not blob_url:
        return
    conn = get_storage_connection_string()
    if not conn:
        return
    try:
        from azure.storage.blob import BlobServiceClient  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("azure-storage-blob not installed; cannot delete blob")
        return
    try:
        parsed = urlparse(blob_url)
        # /container/path/to/blob
        path = parsed.path.lstrip("/")
        if "/" not in path:
            logger.warning("Invalid Azure blob URL for delete: %s", blob_url)
            return
        container, blob_name = path.split("/", 1)
        client = BlobServiceClient.from_connection_string(conn)
        client.get_blob_client(container=container, blob=blob_name).delete_blob()
    except Exception as e:
        logger.warning("Azure blob delete failed for %s: %s", blob_url, e)
