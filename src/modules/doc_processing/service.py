from __future__ import annotations

import hashlib
import logging

from src.modules.doc_processing.chunking import choose_strategy, split_markdown
from src.modules.doc_processing.extractors.local_basic import extract_document
from src.modules.doc_processing.models import ProcessedDocument
from src.modules.doc_processing.repository import derive_document_id, save_processed_document

logger = logging.getLogger(__name__)


async def process_document_part(*, agent_id: str, thread_id: str, event_id: str, part: object) -> ProcessedDocument:
    """Extract a chat attachment into Markdown + chunks. Failures are recorded, never raised."""
    filename = str(getattr(part, "filename", None) or "document")
    mime_type = getattr(part, "mime_type", None)
    data = getattr(part, "data", None) or b""
    doc_id = derive_document_id(agent_id=agent_id, thread_id=thread_id, event_id=event_id, filename=filename)
    base = dict(
        document_id=doc_id,
        agent_id=agent_id,
        thread_id=thread_id,
        event_id=event_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=int(getattr(part, "size_bytes", None) or len(data)),
        sha256=hashlib.sha256(data).hexdigest() if data else "",
    )
    try:
        if not data:
            raise ValueError("Document bytes are not available for extraction.")
        extracted = extract_document(data, filename, mime_type)
        markdown = extracted.markdown.strip()
        if not markdown:
            raise ValueError("No extractable text was found in the document.")
        doc = ProcessedDocument(
            **base,
            strategy=choose_strategy(markdown),
            status="ready",
            markdown=markdown,
            chunks=split_markdown(markdown),
            metadata=extracted.metadata,
            warnings=extracted.warnings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document processing failed filename=%r event=%s: %s", filename, event_id, exc)
        doc = ProcessedDocument(**base, strategy="chunked", status="failed", error=str(exc))
    await save_processed_document(doc)
    return doc
