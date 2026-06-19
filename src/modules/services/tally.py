"""Tally webhook payload parsers for training and recruitment forms."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# TODO: replace placeholder keys with real Tally field keys from your forms.
# Access them in the Tally form editor under «Share → Webhooks → Test payload».
# ---------------------------------------------------------------------------

# Training registration form field keys
TALLY_TREINAMENTO_ID = "question_treinamento_id"
TALLY_UNIDADE_ID = "question_unidade_id"
TALLY_RESPONSAVEL_NOME = "question_responsavel_nome"
TALLY_RESPONSAVEL_TELEFONE = "question_responsavel_telefone"
TALLY_EMAIL_TREINAMENTO = "question_email_treinamento"

# Job application form field keys
TALLY_VAGA_ID = "question_vaga_id"
TALLY_CANDIDATO_NOME = "question_candidato_nome"
TALLY_CANDIDATO_TELEFONE = "question_candidato_telefone"
TALLY_CANDIDATO_EMAIL = "question_candidato_email"
TALLY_CURRICULO_PDF = "question_curriculo_pdf"

# Behavioral assessment form field keys
TALLY_COMPORTAMENTAL_CANDIDATO_ID = "question_candidato_id"
TALLY_COMPORTAMENTAL_RESPOSTAS_PREFIX = "question_comportamental_"


def _extract_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten Tally's ``data.fields`` array into ``{key: value}``."""
    result: dict[str, Any] = {}
    try:
        fields = payload.get("data", {}).get("fields", [])
        if not isinstance(fields, list):
            return result
        for field in fields:
            if not isinstance(field, dict):
                continue
            key = field.get("key") or field.get("label") or ""
            value = field.get("value")
            # For file upload fields, value may be a list of objects with a url
            if key:
                result[str(key)] = value
    except Exception:
        pass
    return result


def parse_inscricao_treinamento(payload: dict[str, Any]) -> dict | None:
    """Parse a Tally training registration webhook payload.

    Returns a dict suitable for inserting into the ``treinamentos`` table, or None if invalid.
    """
    if not isinstance(payload, dict):
        return None

    fields = _extract_fields(payload)
    if not fields:
        return None

    cronograma_id = fields.get(TALLY_TREINAMENTO_ID)
    if not cronograma_id:
        return None

    return {
        "cronograma_id": str(cronograma_id),
        "unidade_id": fields.get(TALLY_UNIDADE_ID) or None,
        "responsavel_nome": fields.get(TALLY_RESPONSAVEL_NOME) or None,
        "responsavel_telefone": fields.get(TALLY_RESPONSAVEL_TELEFONE) or None,
        "email": fields.get(TALLY_EMAIL_TREINAMENTO) or None,
        "resposta": "pendente",
        "arquivado": False,
    }


def parse_candidatura(payload: dict[str, Any]) -> dict | None:
    """Parse a Tally job application webhook payload.

    Returns a dict suitable for inserting into the ``candidatos`` table, or None if invalid.
    Includes ``pdf_url`` extracted from the file upload field.
    """
    if not isinstance(payload, dict):
        return None

    fields = _extract_fields(payload)
    if not fields:
        return None

    vaga_id = fields.get(TALLY_VAGA_ID)
    nome = fields.get(TALLY_CANDIDATO_NOME)
    if not vaga_id or not nome:
        return None

    # Extract PDF URL from file upload field (Tally returns list of {url, name, ...})
    pdf_url: str | None = None
    curriculo_raw = fields.get(TALLY_CURRICULO_PDF)
    if isinstance(curriculo_raw, list) and curriculo_raw:
        first = curriculo_raw[0]
        if isinstance(first, dict):
            pdf_url = first.get("url") or first.get("downloadUrl") or None
    elif isinstance(curriculo_raw, str) and curriculo_raw.startswith("http"):
        pdf_url = curriculo_raw

    return {
        "vaga_id": str(vaga_id),
        "nome": str(nome),
        "telefone": fields.get(TALLY_CANDIDATO_TELEFONE) or None,
        "email": fields.get(TALLY_CANDIDATO_EMAIL) or None,
        "pdf_url": pdf_url,
        "status": "recebido",
        "arquivado": False,
    }


def parse_comportamental(payload: dict[str, Any]) -> dict | None:
    """Parse a Tally behavioral assessment webhook payload.

    Returns a dict with ``candidato_id`` and ``respostas`` (dict of question → answer), or None if invalid.
    """
    if not isinstance(payload, dict):
        return None

    fields = _extract_fields(payload)
    if not fields:
        return None

    candidato_id = fields.get(TALLY_COMPORTAMENTAL_CANDIDATO_ID)
    if not candidato_id:
        return None

    # Collect all behavioral response fields (those starting with the prefix)
    respostas: dict[str, Any] = {}
    for key, value in fields.items():
        if key.startswith(TALLY_COMPORTAMENTAL_RESPOSTAS_PREFIX):
            question_label = key[len(TALLY_COMPORTAMENTAL_RESPOSTAS_PREFIX):]
            respostas[question_label] = value

    return {
        "candidato_id": str(candidato_id),
        "respostas": respostas,
    }
