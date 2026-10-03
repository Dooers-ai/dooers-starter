from __future__ import annotations

from src.modules.doc_processing.models import DocumentChunk, DocumentStrategy

DIRECT_MAX_CHARS = 60_000
CHUNKED_MAX_CHARS = 300_000
CHUNK_MAX_CHARS = 18_000
CHUNK_OVERLAP_CHARS = 1_200


def choose_strategy(markdown: str) -> DocumentStrategy:
    n = len(markdown or "")
    if n <= DIRECT_MAX_CHARS:
        return "direct"
    if n <= CHUNKED_MAX_CHARS:
        return "chunked"
    return "indexed"


def split_markdown(markdown: str, *, max_chars: int = CHUNK_MAX_CHARS) -> list[DocumentChunk]:
    text = (markdown or "").strip()
    if not text:
        return []
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    chunks: list[DocumentChunk] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunk_text = "\n\n".join(current).strip()
        idx = len(chunks)
        chunks.append(
            DocumentChunk(
                chunk_id=f"chunk_{idx:04d}",
                text=chunk_text,
                index=idx,
                char_count=len(chunk_text),
            )
        )
        overlap = chunk_text[-CHUNK_OVERLAP_CHARS:].strip()
        current = [overlap] if overlap else []
        current_len = len(overlap)

    for block in blocks:
        block_len = len(block)
        if block_len > max_chars:
            flush()
            start = 0
            while start < block_len:
                piece = block[start : start + max_chars].strip()
                if piece:
                    idx = len(chunks)
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"chunk_{idx:04d}",
                            text=piece,
                            index=idx,
                            char_count=len(piece),
                        )
                    )
                start += max_chars - CHUNK_OVERLAP_CHARS
            current = []
            current_len = 0
            continue
        if current_len and current_len + block_len + 2 > max_chars:
            flush()
        current.append(block)
        current_len += block_len + 2

    flush()
    return chunks
