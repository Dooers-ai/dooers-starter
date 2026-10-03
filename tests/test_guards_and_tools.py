import pytest

from src.modules.agent.core.execution_guard import is_passive_deferred_action
from src.modules.agent.core.tools import evaluate_expression
from src.modules.doc_processing.models import DocumentChunk, ProcessedDocument
from src.modules.doc_processing.search import render_document_context


@pytest.mark.parametrize(
    "reply",
    ["Vou verificar isso e já retorno.", "Aguarde um instante, por favor.", "I'll check that for you."],
)
def test_passive_replies_detected(reply):
    assert is_passive_deferred_action(reply)


@pytest.mark.parametrize("reply", ["O total é R$ 120,00.", "Here is the summary of your document: ...", ""])
def test_concrete_replies_pass(reply):
    assert not is_passive_deferred_action(reply)


def test_calculator_is_safe():
    assert evaluate_expression("2 + 3 * 4")["result"] == 14
    assert evaluate_expression("sqrt(16) + round(2.6)")["result"] == 7
    assert "error" in evaluate_expression("__import__('os')")
    assert "error" in evaluate_expression("2 ** 10000")


def _doc(doc_id: str, text: str) -> ProcessedDocument:
    return ProcessedDocument(
        document_id=doc_id,
        agent_id="a",
        thread_id="t",
        event_id="e",
        filename=f"{doc_id}.txt",
        mime_type="text/plain",
        size_bytes=len(text),
        sha256="",
        strategy="chunked",
        status="ready",
        markdown=text,
        chunks=[
            DocumentChunk(chunk_id=f"{doc_id}-{i}", index=i, text=part, char_count=len(part)) for i, part in enumerate(text.split("\n\n"))
        ],
    )


def test_document_search_returns_relevant_chunk():
    doc = _doc("d1", "Capítulo 1: preços e descontos.\n\nCapítulo 2: prazo de entrega é 5 dias.\n\nCapítulo 3: garantia.")
    out = render_document_context([doc], query="prazo de entrega", document_id=None, mode="search")
    assert "5 dias" in out
    assert "garantia" not in out


def test_document_search_unknown_id():
    out = render_document_context([_doc("d1", "x")], query="", document_id="nope", mode="search")
    assert "not found" in out
