"""Azure AI Search helpers (index ensure, upload docs, keyword search)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.modules.external.azure.auth import get_ai_search_api_key, get_ai_search_endpoint

logger = logging.getLogger(__name__)

_AZURE_SEARCH_KEY_HELP = (
    "Azure AI Search: invalid URL or API key. Use the resource admin key "
    "(portal: Keys → Admin keys, not Query keys only) and the HTTPS endpoint "
    "(https://<name>.search.windows.net). Set in agent «Documentos (RAG)» or env "
    "AZURE_AI_SEARCH_ENDPOINT / AZURE_AI_SEARCH_API_KEY."
)


def _reraise_auth_as_value_error(exc: BaseException) -> None:
    """Turn auth/config HttpResponseError into ValueError so upload routes return 400."""
    try:
        from azure.core.exceptions import HttpResponseError  # type: ignore[import-untyped]
    except ImportError:
        return
    if not isinstance(exc, HttpResponseError):
        return
    status = int(getattr(exc, "status_code", None) or 0)
    text = f"{exc.message or ''} {exc}".lower()
    if status in {401, 403} or "key" in text or "credential" in text or "unauthorized" in text:
        raise ValueError(_AZURE_SEARCH_KEY_HELP) from exc


def _clients(index_name: str, agent_settings: dict[str, Any] | None):
    endpoint = get_ai_search_endpoint(agent_settings)
    key = get_ai_search_api_key(agent_settings)
    if not endpoint or not key:
        raise RuntimeError("Azure AI Search endpoint/key not configured")
    try:
        from azure.core.credentials import AzureKeyCredential  # type: ignore[import-untyped]
        from azure.search.documents import SearchClient  # type: ignore[import-untyped]
        from azure.search.documents.indexes import SearchIndexClient  # type: ignore[import-untyped]
    except ImportError as e:
        raise RuntimeError("azure-search-documents not installed") from e
    cred = AzureKeyCredential(key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=cred)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=cred)
    return index_client, search_client


def _sync_ensure_agent_index(index_name: str, agent_settings: dict[str, Any] | None) -> None:
    try:
        index_client, _ = _clients(index_name, agent_settings)
        names = [n.lower() for n in index_client.list_index_names()]
        if index_name.lower() in names:
            return
        from azure.search.documents.indexes.models import (  # type: ignore[import-untyped]
            SearchField,
            SearchFieldDataType,
            SearchIndex,
            SimpleField,
        )

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchField(name="agent_id", type=SearchFieldDataType.String, searchable=False, filterable=True),
            SearchField(name="filename", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="source", type=SearchFieldDataType.String, searchable=False, filterable=True),
            SearchField(name="field_id", type=SearchFieldDataType.String, searchable=False, filterable=True),
            SearchField(name="thread_id", type=SearchFieldDataType.String, searchable=False, filterable=True),
            SearchField(name="blob_url", type=SearchFieldDataType.String, searchable=False),
        ]
        index_client.create_index(SearchIndex(name=index_name, fields=fields))
    except ValueError:
        raise
    except Exception as e:
        _reraise_auth_as_value_error(e)
        raise


async def ensure_agent_index(index_name: str, agent_settings: dict[str, Any] | None = None) -> None:
    await asyncio.to_thread(_sync_ensure_agent_index, index_name, agent_settings)


def _raise_if_indexing_failed(results: Any, *, index_name: str) -> None:
    """Azure returns HTTP 207 for mixed batch outcomes; the SDK still returns without raising."""
    if not results:
        return
    for r in results:
        ok = getattr(r, "succeeded", None)
        if ok is None and isinstance(r, dict):
            ok = r.get("succeeded")
        if ok:
            continue
        key = getattr(r, "key", None) or (r.get("key") if isinstance(r, dict) else "")
        err = getattr(r, "error_message", None) or (r.get("error_message") if isinstance(r, dict) else None)
        code = getattr(r, "status_code", None) or (r.get("status_code") if isinstance(r, dict) else None)
        detail = f"{err or 'unknown'} (status={code})" if code is not None else (err or "unknown")
        logger.error(
            "Azure AI Search indexing failed index=%s key=%r detail=%s",
            index_name,
            key,
            detail,
        )
        raise ValueError(f"Azure AI Search indexing failed for index '{index_name}' document id={key!r}: {detail}")


def _sync_upload_documents(
    index_name: str,
    docs: list[dict[str, Any]],
    agent_settings: dict[str, Any] | None,
    *,
    ensure_index_exists: bool = True,
) -> None:
    try:
        if ensure_index_exists:
            _sync_ensure_agent_index(index_name, agent_settings)
        _, search_client = _clients(index_name, agent_settings)
        results = search_client.upload_documents(documents=docs)
        _raise_if_indexing_failed(results, index_name=index_name)
    except ValueError:
        raise
    except Exception as e:
        _reraise_auth_as_value_error(e)
        raise


async def upload_documents(
    index_name: str,
    docs: list[dict[str, Any]],
    *,
    agent_settings: dict[str, Any] | None = None,
    ensure_index_exists: bool = True,
) -> None:
    await asyncio.to_thread(
        lambda: _sync_upload_documents(
            index_name,
            docs,
            agent_settings,
            ensure_index_exists=ensure_index_exists,
        ),
    )


def _sync_delete_documents(
    index_name: str,
    doc_ids: list[str],
    agent_settings: dict[str, Any] | None,
) -> None:
    if not doc_ids:
        return
    try:
        _sync_ensure_agent_index(index_name, agent_settings)
        _, search_client = _clients(index_name, agent_settings)
        to_remove = [{"id": d} for d in doc_ids if d]
        results = search_client.delete_documents(documents=to_remove)
        if results is None:
            raise RuntimeError(
                f"Azure AI Search delete_documents returned None for index {index_name!r} — unable to verify outcome"
            )
        _raise_if_indexing_failed(results, index_name=index_name)
    except ValueError:
        raise
    except Exception as e:
        _reraise_auth_as_value_error(e)
        raise


async def delete_documents(
    index_name: str,
    doc_ids: list[str],
    *,
    agent_settings: dict[str, Any] | None = None,
) -> None:
    await asyncio.to_thread(_sync_delete_documents, index_name, doc_ids, agent_settings)


def _sync_get_document(
    index_name: str,
    doc_id: str,
    agent_settings: dict[str, Any] | None,
) -> dict[str, Any]:
    _, search_client = _clients(index_name, agent_settings)
    return dict(search_client.get_document(doc_id))


async def get_document(
    index_name: str,
    doc_id: str,
    *,
    agent_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(_sync_get_document, index_name, doc_id, agent_settings)


def _sync_search_documents(
    index_name: str,
    query: str,
    max_results: int,
    agent_id: str,
    field_id: str | None,
    agent_settings: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    try:
        _, search_client = _clients(index_name, agent_settings)
        escaped_agent_id = agent_id.replace("'", "''")
        filters = [f"agent_id eq '{escaped_agent_id}'"]
        if field_id:
            escaped_field_id = field_id.replace("'", "''")
            filters.append(f"field_id eq '{escaped_field_id}'")
        results = search_client.search(
            search_text=query,
            top=max_results,
            filter=" and ".join(filters),
            select=["id", "filename", "content", "blob_url"],
        )
        out: list[dict[str, Any]] = []
        for r in results:
            out.append(dict(r))
        return out
    except ValueError:
        raise
    except Exception as e:
        _reraise_auth_as_value_error(e)
        logger.warning("Azure AI Search query failed: %s", e)
        return []


async def search_documents(
    *,
    index_name: str,
    query: str,
    max_results: int,
    agent_id: str,
    field_id: str | None = None,
    agent_settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(
            _sync_search_documents,
            index_name,
            query,
            max_results,
            agent_id,
            field_id,
            agent_settings,
        )
    except ValueError:
        raise
    except Exception as e:
        logger.warning("Azure AI Search query failed: %s", e)
        return []
