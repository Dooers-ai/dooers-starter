from __future__ import annotations

from src.modules.doc_processing.models import ProcessedDocument


def build_document_manifest(documents: list[ProcessedDocument]) -> str:
    ready = [doc for doc in documents if doc.status == "ready"]
    if not ready:
        return ""
    lines = ["Documents attached to this thread:"]
    for doc in ready[:20]:
        meta = doc.metadata or {}
        bits: list[str] = []
        if meta.get("kind"):
            bits.append(str(meta["kind"]))
        if meta.get("pages"):
            bits.append(f"{meta['pages']} pages")
        if isinstance(meta.get("sheets"), list):
            bits.append("sheets: " + ", ".join(str(s) for s in meta["sheets"][:6]))
        if meta.get("ocr_required"):
            bits.append("OCR pending")
        detail = f" ({'; '.join(bits)})" if bits else ""
        lines.append(f"- {doc.filename} [document_id={doc.document_id}, strategy={doc.strategy}]{detail}")
    lines.append(
        "Call `get_thread_document_context` whenever the answer depends on these documents. "
        "Do not invent document details without reading them."
    )
    return "\n".join(lines)


def summarize_document_for_note(doc: ProcessedDocument) -> str:
    if doc.status != "ready":
        return f"[Documento {doc.filename} recebido, mas não pôde ser processado: {doc.error or 'erro desconhecido'}]"
    kind = (doc.metadata or {}).get("kind") or "documento"
    return (
        f"[Documento recebido e processado: {doc.filename} "
        f"(document_id={doc.document_id}, tipo={kind}). Conteúdo disponível via get_thread_document_context.]"
    )
