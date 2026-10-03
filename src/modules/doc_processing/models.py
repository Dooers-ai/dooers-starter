from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DocumentStrategy = Literal["direct", "chunked", "indexed"]
DocumentStatus = Literal["ready", "failed"]


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    index: int
    char_count: int


@dataclass(slots=True)
class ExtractedDocument:
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProcessedDocument:
    document_id: str
    agent_id: str
    thread_id: str
    event_id: str
    filename: str
    mime_type: str | None
    size_bytes: int
    sha256: str
    strategy: DocumentStrategy
    status: DocumentStatus
    markdown: str = ""
    chunks: list[DocumentChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessedDocument:
        chunks = [
            DocumentChunk(
                chunk_id=str(c.get("chunk_id") or ""),
                text=str(c.get("text") or ""),
                index=int(c.get("index") or 0),
                char_count=int(c.get("char_count") or len(str(c.get("text") or ""))),
            )
            for c in data.get("chunks", [])
            if isinstance(c, dict)
        ]
        return cls(
            document_id=str(data.get("document_id") or ""),
            agent_id=str(data.get("agent_id") or ""),
            thread_id=str(data.get("thread_id") or ""),
            event_id=str(data.get("event_id") or ""),
            filename=str(data.get("filename") or "document"),
            mime_type=data.get("mime_type"),
            size_bytes=int(data.get("size_bytes") or 0),
            sha256=str(data.get("sha256") or ""),
            strategy=data.get("strategy") if data.get("strategy") in {"direct", "chunked", "indexed"} else "chunked",
            status=data.get("status") if data.get("status") in {"ready", "failed"} else "failed",
            markdown=str(data.get("markdown") or ""),
            chunks=chunks,
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            warnings=[str(w) for w in data.get("warnings", []) if w is not None],
            error=str(data.get("error")) if data.get("error") else None,
        )
