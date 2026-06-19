"""Recruitment service — candidate pipeline, AI PDF analysis, and behavioral profile generation."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import httpx
from supabase import AsyncClient

from src.modules.services.constants import (
    STATUS_ANALISADO,
    STATUS_CONTATADO,
    TABELA_CANDIDATOS,
    TABELA_VAGAS,
)

logger = logging.getLogger(__name__)

_ANALISE_SYSTEM_PROMPT = """Você é um recrutador sênior especializado em estética e franquias de beleza.
Analise o currículo a seguir e avalie a adequação do candidato para uma vaga no setor de estética/beleza.

Retorne APENAS um JSON válido com os campos:
- "nota": número inteiro de 0 a 10 representando a adequação geral
- "justificativa": string com até 300 caracteres explicando a nota

Exemplo: {"nota": 7, "justificativa": "Candidato tem experiência relevante em estética, mas sem cursos formais."}
"""

_COMPORTAMENTAL_SYSTEM_PROMPT = """Você é um especialista em psicologia organizacional e recrutamento comportamental.
Com base nas respostas do candidato ao formulário comportamental, elabore um perfil comportamental conciso (máximo 500 palavras).

Identifique:
1. Estilo de comunicação e relacionamento interpessoal
2. Motivadores e valores profissionais
3. Pontos fortes para o ambiente de franquias de estética
4. Possíveis pontos de atenção

Responda em português do Brasil, em formato de texto corrido profissional.
"""


async def baixar_e_extrair_texto_pdf(url: str) -> str:
    """Download PDF from URL and extract text content using pypdf."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content

        from pypdf import PdfReader  # type: ignore[import-untyped]

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
        text = "\n\n".join(t for t in pages if t)
        return text or "[PDF sem texto extraível]"
    except Exception as exc:
        logger.warning("baixar_e_extrair_texto_pdf falhou url=%s: %s", url, exc)
        return ""


async def listar_vagas(
    supabase: AsyncClient,
    apenas_ativas: bool = True,
) -> list[dict]:
    """List job positions. Optionally filter to active only."""
    try:
        query = supabase.table(TABELA_VAGAS).select("*").eq("arquivado", False)
        if apenas_ativas:
            query = query.eq("ativa", True)
        result = await query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception:
        logger.exception("listar_vagas falhou")
        return []


async def listar_candidatos(
    supabase: AsyncClient,
    vaga_id: str,
    status: str = "",
) -> list[dict]:
    """List candidates for a position. Optionally filter by status. Ordered by nota desc."""
    try:
        query = (
            supabase.table(TABELA_CANDIDATOS)
            .select("*")
            .eq("vaga_id", vaga_id)
            .eq("arquivado", False)
        )
        if status:
            query = query.eq("status", status)
        result = await query.order("nota", desc=True, nullsfirst=False).execute()
        return result.data or []
    except Exception:
        logger.exception("listar_candidatos falhou vaga_id=%s", vaga_id)
        return []


async def buscar_candidato(
    supabase: AsyncClient,
    candidato_id: str,
) -> dict | None:
    """Fetch a single candidate with joined position data (titulo, descricao)."""
    try:
        result = await (
            supabase.table(TABELA_CANDIDATOS)
            .select("*, vagas(titulo, descricao)")
            .eq("id", candidato_id)
            .eq("arquivado", False)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None
    except Exception:
        logger.exception("buscar_candidato falhou id=%s", candidato_id)
        return None


async def garantir_analise_pdf(
    supabase: AsyncClient,
    candidato: dict[str, Any],
    openai_api_key: str,
) -> dict[str, Any]:
    """If candidate hasn't been scored yet, download PDF, extract text, call GPT-4o for analysis, persist, return updated candidate."""
    if candidato.get("nota") is not None:
        return candidato

    pdf_url = candidato.get("pdf_url") or ""
    candidato_id = candidato.get("id") or ""

    if not pdf_url:
        logger.info("garantir_analise_pdf: candidato %s sem pdf_url", candidato_id)
        return candidato

    texto = candidato.get("texto_pdf") or ""
    if not texto:
        texto = await baixar_e_extrair_texto_pdf(pdf_url)
        if texto:
            # Persist extracted text
            try:
                await (
                    supabase.table(TABELA_CANDIDATOS)
                    .update({"texto_pdf": texto})
                    .eq("id", candidato_id)
                    .execute()
                )
            except Exception:
                logger.warning("Falha ao persistir texto_pdf candidato=%s", candidato_id)

    if not texto:
        return candidato

    import json as _json

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _ANALISE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Currículo:\n\n{texto[:8000]}"},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = _json.loads(raw)
        nota = int(parsed.get("nota", 0))
        justificativa = str(parsed.get("justificativa", ""))

        await (
            supabase.table(TABELA_CANDIDATOS)
            .update({"nota": nota, "justificativa": justificativa, "status": STATUS_ANALISADO})
            .eq("id", candidato_id)
            .execute()
        )
        return {**candidato, "nota": nota, "justificativa": justificativa, "status": STATUS_ANALISADO}
    except Exception:
        logger.exception("garantir_analise_pdf GPT-4o falhou candidato=%s", candidato_id)
        return candidato


async def analisar_candidaturas_em_background(
    supabase: AsyncClient,
    candidato_ids: list[str],
    openai_api_key: str,
) -> None:
    """Analyze multiple candidates in background, one at a time with small delay to avoid thundering herd."""
    for candidato_id in candidato_ids:
        try:
            candidato = await buscar_candidato(supabase, candidato_id)
            if candidato:
                await garantir_analise_pdf(supabase, candidato, openai_api_key)
        except Exception:
            logger.exception("analisar_candidaturas_em_background falhou candidato=%s", candidato_id)
        await asyncio.sleep(0.1)


async def contatar_candidato_atomico(
    supabase: AsyncClient,
    candidato_id: str,
) -> bool:
    """Atomically mark candidate as contacted only if not already contacted.

    Uses .neq("status", STATUS_CONTATADO) conditional update to avoid double-contact.
    Returns True if the update actually changed a row.
    """
    try:
        result = await (
            supabase.table(TABELA_CANDIDATOS)
            .update({"status": STATUS_CONTATADO})
            .eq("id", candidato_id)
            .neq("status", STATUS_CONTATADO)
            .eq("arquivado", False)
            .execute()
        )
        updated = result.data or []
        return len(updated) > 0
    except Exception:
        logger.exception("contatar_candidato_atomico falhou id=%s", candidato_id)
        return False


async def soft_delete_candidato(
    supabase: AsyncClient,
    candidato_id: str,
) -> bool:
    """Soft-delete a candidate record."""
    try:
        await (
            supabase.table(TABELA_CANDIDATOS)
            .update({"arquivado": True})
            .eq("id", candidato_id)
            .execute()
        )
        return True
    except Exception:
        logger.exception("soft_delete_candidato falhou id=%s", candidato_id)
        return False


async def soft_undelete_candidato(
    supabase: AsyncClient,
    candidato_id: str,
) -> bool:
    """Undo soft-delete for a candidate record."""
    try:
        await (
            supabase.table(TABELA_CANDIDATOS)
            .update({"arquivado": False})
            .eq("id", candidato_id)
            .execute()
        )
        return True
    except Exception:
        logger.exception("soft_undelete_candidato falhou id=%s", candidato_id)
        return False


async def salvar_perfil_comportamental(
    supabase: AsyncClient,
    candidato_id: str,
    perfil: str,
) -> bool:
    """Persist behavioral profile text for a candidate."""
    try:
        await (
            supabase.table(TABELA_CANDIDATOS)
            .update({"perfil_comportamental": perfil, "status": "comportamental_recebido"})
            .eq("id", candidato_id)
            .execute()
        )
        return True
    except Exception:
        logger.exception("salvar_perfil_comportamental falhou id=%s", candidato_id)
        return False


async def gerar_perfil_comportamental(
    respostas: dict[str, Any],
    openai_api_key: str,
) -> str:
    """Call GPT-4o with behavioral assessment responses and return a text profile."""
    if not respostas:
        return ""

    respostas_texto = "\n".join(f"- {k}: {v}" for k, v in respostas.items())
    user_content = f"Respostas do candidato ao formulário comportamental:\n\n{respostas_texto}"

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _COMPORTAMENTAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=700,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("gerar_perfil_comportamental falhou")
        return ""
