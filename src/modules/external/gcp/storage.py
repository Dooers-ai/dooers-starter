"""Upload blobs to GCS when GCP_BUCKET_NAME is set."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import BinaryIO

from src.config import settings

logger = logging.getLogger(__name__)


def upload_bytes_to_blob_name(data: bytes, blob_name: str, content_type: str | None = None) -> str | None:
    """Upload to ``gs://bucket/{blob_name}``. Returns gs:// URI or None if bucket missing / error."""
    bucket_name = (settings.gcp_bucket_name or "").strip()
    if not bucket_name or not blob_name.strip():
        return None
    try:
        from google.cloud import storage  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("google-cloud-storage not available")
        return None

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name.strip())
    blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
    uri = f"gs://{bucket_name}/{blob_name.strip()}"
    logger.info("Uploaded to %s", uri)
    return uri


def upload_bytes(data: bytes, filename: str, content_type: str | None = None) -> str | None:
    """
    Upload to gs://bucket/agent-template/{uuid}_{filename}.
    Returns gs:// URI or None if bucket not configured / error.
    """
    safe_name = filename.replace("/", "_") or "file"
    blob_name = f"agent-template/{uuid.uuid4().hex}_{safe_name}"
    return upload_bytes_to_blob_name(data, blob_name, content_type)


def upload_fileobj(fp: BinaryIO, filename: str, content_type: str | None = None) -> str | None:
    data = fp.read()
    return upload_bytes(data, filename, content_type)


def generate_signed_get_url(blob_name: str, expiration_minutes: int = 60) -> str | None:
    """Return a time-limited HTTPS URL for reading an object, or None if unavailable."""
    bucket_name = (settings.gcp_bucket_name or "").strip()
    if not bucket_name or not blob_name.strip():
        return None
    try:
        from google.cloud import storage  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("google-cloud-storage not available")
        return None
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name.strip())
        return blob.generate_signed_url(
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            version="v4",
        )
    except Exception as e:
        logger.warning("GCS signed URL failed for %s: %s", blob_name, e)
        return None


def delete_gs_uri(gs_uri: str | None) -> None:
    """Best-effort delete for gs://bucket/object paths returned by upload_bytes."""
    if not gs_uri or not gs_uri.startswith("gs://"):
        return
    try:
        from google.cloud import storage  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("google-cloud-storage not available")
        return
    without = gs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    if not bucket_name or not blob_name:
        logger.warning("Invalid gs:// URI for delete: %s", gs_uri)
        return
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        bucket.blob(blob_name).delete()
        logger.info("Deleted GCS object %s", gs_uri)
    except Exception as e:
        logger.warning("GCS delete failed for %s: %s", gs_uri, e)
