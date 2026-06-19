"""Training management service — all functions are async and receive supabase as first arg."""

from __future__ import annotations

import logging
from typing import Any

from supabase import AsyncClient

from src.modules.services.constants import (
    RESPOSTA_PENDENTE,
    TABELA_CRONOGRAMA,
    TABELA_INSCRICOES,
    TABELA_UNIDADES,
)

logger = logging.getLogger(__name__)

# Allowlist of tables that support soft delete in this service
_SOFT_DELETE_TABLES = frozenset({TABELA_CRONOGRAMA, TABELA_INSCRICOES, TABELA_UNIDADES})


async def listar_cronograma(
    supabase: AsyncClient,
    mes_ano: str = "",
    apenas_ativos: bool = True,
) -> list[dict]:
    """List training schedule entries. Filter by month/year in MM/YYYY format when provided."""
    try:
        query = supabase.table(TABELA_CRONOGRAMA).select("*").eq("arquivado", False)
        if apenas_ativos:
            query = query.eq("ativo", True)
        if mes_ano and len(mes_ano) == 7 and mes_ano[2] == "/":
            mes, ano = mes_ano[:2], mes_ano[3:]
            # Filter: data starts with YYYY-MM
            data_prefix = f"{ano}-{mes}"
            query = query.gte("data", f"{data_prefix}-01").lt("data", f"{data_prefix}-32")
        result = await query.order("data").execute()
        return result.data or []
    except Exception:
        logger.exception("listar_cronograma falhou")
        return []


async def buscar_treinamento(
    supabase: AsyncClient,
    treinamento_id: str,
) -> dict | None:
    """Fetch a single training schedule entry by ID."""
    try:
        result = await (
            supabase.table(TABELA_CRONOGRAMA)
            .select("*")
            .eq("id", treinamento_id)
            .eq("arquivado", False)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None
    except Exception:
        logger.exception("buscar_treinamento falhou id=%s", treinamento_id)
        return None


async def listar_inscricoes(
    supabase: AsyncClient,
    cronograma_id: str,
    apenas_pendentes: bool = False,
) -> list[dict]:
    """List attendance records for a given training. Optionally filter to pending only."""
    try:
        query = (
            supabase.table(TABELA_INSCRICOES)
            .select("*, unidades(nome, telefone)")
            .eq("cronograma_id", cronograma_id)
            .eq("arquivado", False)
        )
        if apenas_pendentes:
            query = query.eq("resposta", RESPOSTA_PENDENTE)
        result = await query.execute()
        return result.data or []
    except Exception:
        logger.exception("listar_inscricoes falhou cronograma_id=%s", cronograma_id)
        return []


async def buscar_unidade_por_telefone(
    supabase: AsyncClient,
    telefone: str,
) -> dict | None:
    """Look up a franchise unit by phone number (E.164 or local format)."""
    try:
        # Try exact match first
        result = await (
            supabase.table(TABELA_UNIDADES)
            .select("*")
            .eq("telefone", telefone)
            .eq("arquivado", False)
            .limit(1)
            .execute()
        )
        data = result.data or []
        if data:
            return data[0]
        # Try without leading + (some systems strip it)
        normalized = telefone.lstrip("+")
        result2 = await (
            supabase.table(TABELA_UNIDADES)
            .select("*")
            .eq("telefone", normalized)
            .eq("arquivado", False)
            .limit(1)
            .execute()
        )
        data2 = result2.data or []
        return data2[0] if data2 else None
    except Exception:
        logger.exception("buscar_unidade_por_telefone falhou telefone=%s", telefone)
        return None


async def listar_inscricoes_por_unidade(
    supabase: AsyncClient,
    unidade_id: str,
    apenas_pendentes: bool = False,
) -> list[dict]:
    """List all attendance records for a given unit. Optionally filter to pending only."""
    try:
        query = (
            supabase.table(TABELA_INSCRICOES)
            .select("*, cronograma(nome, data)")
            .eq("unidade_id", unidade_id)
            .eq("arquivado", False)
        )
        if apenas_pendentes:
            query = query.eq("resposta", RESPOSTA_PENDENTE)
        result = await query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception:
        logger.exception("listar_inscricoes_por_unidade falhou unidade_id=%s", unidade_id)
        return []


async def registrar_resposta_presenca(
    supabase: AsyncClient,
    inscricao_id: str,
    resposta: str,
) -> bool:
    """Register a unit's attendance response (sim/nao/pendente) by inscription ID."""
    try:
        await (
            supabase.table(TABELA_INSCRICOES)
            .update({"resposta": resposta})
            .eq("id", inscricao_id)
            .eq("arquivado", False)
            .execute()
        )
        return True
    except Exception:
        logger.exception(
            "registrar_resposta_presenca falhou inscricao_id=%s",
            inscricao_id,
        )
        return False


async def relatorio_presenca(
    supabase: AsyncClient,
    cronograma_id: str,
) -> dict[str, Any]:
    """Build attendance report for a training. Returns totals and per-status detail lists."""
    try:
        inscricoes = await listar_inscricoes(supabase, cronograma_id)
        confirmados = [i for i in inscricoes if i.get("resposta") == "sim"]
        recusados = [i for i in inscricoes if i.get("resposta") == "nao"]
        pendentes = [i for i in inscricoes if i.get("resposta") == RESPOSTA_PENDENTE]
        return {
            "total": len(inscricoes),
            "confirmados": len(confirmados),
            "recusados": len(recusados),
            "pendentes": len(pendentes),
            "detalhes_confirmados": confirmados,
            "detalhes_recusados": recusados,
            "detalhes_pendentes": pendentes,
        }
    except Exception:
        logger.exception("relatorio_presenca falhou cronograma_id=%s", cronograma_id)
        return {
            "total": 0,
            "confirmados": 0,
            "recusados": 0,
            "pendentes": 0,
            "detalhes_confirmados": [],
            "detalhes_recusados": [],
            "detalhes_pendentes": [],
        }


async def soft_delete(
    supabase: AsyncClient,
    tabela: str,
    registro_id: str,
) -> bool:
    """Soft-delete a record (set arquivado=True). Only allows tables in TABELA_* constants."""
    if tabela not in _SOFT_DELETE_TABLES:
        logger.warning("soft_delete: tabela '%s' não permitida", tabela)
        return False
    try:
        await (
            supabase.table(tabela)
            .update({"arquivado": True})
            .eq("id", registro_id)
            .execute()
        )
        return True
    except Exception:
        logger.exception("soft_delete falhou tabela=%s id=%s", tabela, registro_id)
        return False


async def soft_undelete(
    supabase: AsyncClient,
    tabela: str,
    registro_id: str,
) -> bool:
    """Undo soft-delete (set arquivado=False). Only allows tables in TABELA_* constants."""
    if tabela not in _SOFT_DELETE_TABLES:
        logger.warning("soft_undelete: tabela '%s' não permitida", tabela)
        return False
    try:
        await (
            supabase.table(tabela)
            .update({"arquivado": False})
            .eq("id", registro_id)
            .execute()
        )
        return True
    except Exception:
        logger.exception("soft_undelete falhou tabela=%s id=%s", tabela, registro_id)
        return False
