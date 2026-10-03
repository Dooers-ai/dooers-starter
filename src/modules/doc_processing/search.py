"""Deterministic lookup inside processed thread documents (no LLM, no network)."""

from __future__ import annotations

import re
from collections import Counter

from src.modules.doc_processing.models import DocumentChunk, ProcessedDocument

_WORD_RE = re.compile(r"[\wÀ-ÿ]{3,}", re.UNICODE)
FULL_TEXT_MAX_CHARS = 60_000


def _tokens(text: str) -> Counter[str]:
    return Counter(token.lower() for token in _WORD_RE.findall(text or ""))


def _score(query_tokens: Counter[str], chunk: DocumentChunk) -> int:
    if not query_tokens:
        return 0
    chunk_tokens = _tokens(chunk.text)
    return sum(min(count, chunk_tokens.get(token, 0)) for token, count in query_tokens.items())


def select_chunks(doc: ProcessedDocument, query: str, *, top_k: int = 6) -> list[DocumentChunk]:
    if not doc.chunks:
        return []
    query_tokens = _tokens(query)
    ranked = sorted(doc.chunks, key=lambda chunk: (_score(query_tokens, chunk), -chunk.index), reverse=True)
    selected = [chunk for chunk in ranked if _score(query_tokens, chunk) > 0][:top_k]
    if selected:
        return sorted(selected, key=lambda chunk: chunk.index)
    return doc.chunks[: min(top_k, len(doc.chunks))]


def render_document_context(documents: list[ProcessedDocument], *, query: str, document_id: str | None, mode: str) -> str:
    docs = {doc.document_id: doc for doc in documents if doc.status == "ready"}
    candidates = list(docs.values())
    if document_id and document_id.strip():
        doc = docs.get(document_id.strip())
        if not doc:
            return f"Document {document_id!r} not found in this thread. Available: {', '.join(docs) or 'none'}"
        candidates = [doc]
    if not candidates:
        return "There are no processed documents in this thread."

    requested = (mode or "search").strip().lower()
    outputs: list[str] = []
    for doc in candidates[:5]:
        head = f"{doc.filename} (document_id={doc.document_id})"
        if requested == "summary":
            outputs.append(f"Preview of {head}:\n\n{doc.markdown[:4000].strip()}")
        elif requested == "full" or (doc.strategy == "direct" and not query.strip()):
            if len(doc.markdown) <= FULL_TEXT_MAX_CHARS:
                outputs.append(f"Full content of {head}:\n\n{doc.markdown}")
            else:
                outputs.append(f"{head} is too large for full mode; showing the first part:\n\n{doc.markdown[:FULL_TEXT_MAX_CHARS]}")
        else:
            chunks = select_chunks(doc, query or doc.filename)
            body = "\n".join(f"\n[chunk {chunk.index + 1}]\n{chunk.text}" for chunk in chunks)
            outputs.append(f"Excerpts from {head}:{body}")
    return "\n\n---\n\n".join(outputs).strip()
