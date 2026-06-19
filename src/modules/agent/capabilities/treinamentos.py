"""Training management capability — 9 tools for the franchise training workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from agents import Agent, RunContextWrapper, function_tool

from src.modules.agent.agent_context import AgentRunContext
from src.modules.services import treinamentos_service as svc
from src.modules.services.constants import TABELA_CRONOGRAMA, TABELA_INSCRICOES, TABELA_UNIDADES

logger = logging.getLogger(__name__)

_TABELAS_PERMITIDAS = frozenset({TABELA_CRONOGRAMA, TABELA_INSCRICOES, TABELA_UNIDADES})


def _montar_msg_confirmacao(treinamento: dict) -> str:
    """Build WhatsApp confirmation request message with bold formatting."""
    nome = treinamento.get("nome", "Treinamento")
    data = treinamento.get("data", "")
    tipo = treinamento.get("tipo", "")
    descricao = treinamento.get("descricao", "")

    linhas = [
        f"*Confirmação de Presença — {nome}*",
        "",
        f"📅 Data: *{data}*",
        f"📍 Tipo: *{tipo.capitalize() if tipo else 'N/A'}*",
    ]
    if descricao:
        linhas.append(f"ℹ️ {descricao}")
    linhas += [
        "",
        "Por favor, confirme a presença de sua unidade respondendo:",
        "✅ *SIM* — confirmar presença",
        "❌ *NÃO* — recusar presença",
    ]
    return "\n".join(linhas)


def _montar_msg_ativacao(treinamento: dict, mensagem_customizada: str = "") -> str:
    """Build WhatsApp activation/announcement message with emojis."""
    nome = treinamento.get("nome", "Treinamento")
    data = treinamento.get("data", "")
    tipo = treinamento.get("tipo", "")
    descricao = treinamento.get("descricao", "")

    if mensagem_customizada:
        return mensagem_customizada

    linhas = [
        f"🎓 *Novo Treinamento Disponível!*",
        "",
        f"📚 *{nome}*",
        f"📅 Data: {data}",
        f"📍 Modalidade: {tipo.capitalize() if tipo else 'N/A'}",
    ]
    if descricao:
        linhas.append(f"\n{descricao}")
    linhas += [
        "",
        "Fique atento às próximas comunicações para confirmação de presença.",
        "Dúvidas? Entre em contato com a gestão de treinamentos.",
    ]
    return "\n".join(linhas)


@function_tool
async def consultar_cronograma(
    ctx: RunContextWrapper[AgentRunContext],
    mes_ano: str = "",
) -> str:
    """Consulta o cronograma de treinamentos. Use mes_ano no formato MM/YYYY para filtrar (ex: 05/2025). Deixe vazio para listar todos os próximos."""
    try:
        items = await svc.listar_cronograma(ctx.context.supabase, mes_ano=mes_ano)
        if not items:
            return json.dumps({"treinamentos": [], "mensagem": "Nenhum treinamento encontrado."}, ensure_ascii=False)
        return json.dumps({"treinamentos": items}, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("consultar_cronograma falhou")
        return json.dumps({"erro": "Falha ao consultar o cronograma."}, ensure_ascii=False)


@function_tool
async def detalhar_treinamento(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
) -> str:
    """Retorna os detalhes de um treinamento específico, incluindo a lista de inscrições."""
    try:
        treinamento = await svc.buscar_treinamento(ctx.context.supabase, treinamento_id)
        if not treinamento:
            return json.dumps({"erro": f"Treinamento {treinamento_id} não encontrado."}, ensure_ascii=False)
        inscricoes = await svc.listar_inscricoes(ctx.context.supabase, treinamento_id)
        return json.dumps(
            {"treinamento": treinamento, "inscricoes": inscricoes},
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        logger.exception("detalhar_treinamento falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao detalhar o treinamento."}, ensure_ascii=False)


@function_tool
async def preview_confirmacao_presenca(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
) -> str:
    """Mostra um preview da mensagem de confirmação de presença e a lista de destinatários ANTES de enviar.

    IMPORTANTE: Sempre chame esta ferramenta primeiro e apresente o preview ao usuário para aprovação.
    Só envie após confirmação explícita do usuário.
    """
    try:
        treinamento = await svc.buscar_treinamento(ctx.context.supabase, treinamento_id)
        if not treinamento:
            return json.dumps({"erro": f"Treinamento {treinamento_id} não encontrado."}, ensure_ascii=False)
        pendentes = await svc.listar_inscricoes(ctx.context.supabase, treinamento_id, apenas_pendentes=True)
        msg = _montar_msg_confirmacao(treinamento)
        destinatarios = [
            {
                "unidade": i.get("unidades", {}).get("nome") if isinstance(i.get("unidades"), dict) else i.get("responsavel_nome"),
                "telefone": i.get("unidades", {}).get("telefone") if isinstance(i.get("unidades"), dict) else i.get("responsavel_telefone"),
            }
            for i in pendentes
        ]
        return json.dumps(
            {
                "preview": True,
                "mensagem_exemplo": msg,
                "total_destinatarios": len(pendentes),
                "destinatarios": destinatarios,
                "instrucao": "Confirme para enviar com a ferramenta 'enviar_confirmacao_presenca'.",
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        logger.exception("preview_confirmacao_presenca falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao gerar preview."}, ensure_ascii=False)


@function_tool
async def enviar_confirmacao_presenca(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
) -> str:
    """Envia mensagem de confirmação de presença pelo WhatsApp para todas as unidades com resposta pendente.

    IMPORTANTE: Só chame esta ferramenta após mostrar o preview (preview_confirmacao_presenca) e o usuário confirmar o envio.
    """
    try:
        treinamento = await svc.buscar_treinamento(ctx.context.supabase, treinamento_id)
        if not treinamento:
            return json.dumps({"erro": f"Treinamento {treinamento_id} não encontrado."}, ensure_ascii=False)
        pendentes = await svc.listar_inscricoes(ctx.context.supabase, treinamento_id, apenas_pendentes=True)
        if not pendentes:
            return json.dumps({"mensagem": "Nenhuma inscrição pendente para este treinamento."}, ensure_ascii=False)

        msg = _montar_msg_confirmacao(treinamento)
        enviados = 0
        falhas = 0

        for inscricao in pendentes:
            unidade_info = inscricao.get("unidades") or {}
            telefone = (
                unidade_info.get("telefone") if isinstance(unidade_info, dict) else None
            ) or inscricao.get("responsavel_telefone") or ""

            if not telefone:
                falhas += 1
                continue

            ctx.context.pending_whatsapp_sends.append({"to_phone": telefone, "message": msg})
            enviados += 1

        return json.dumps(
            {
                "enviados": enviados,
                "falhas": falhas,
                "total_tentativas": len(pendentes),
            },
            ensure_ascii=False,
        )
    except Exception:
        logger.exception("enviar_confirmacao_presenca falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao enviar confirmações."}, ensure_ascii=False)


@function_tool
async def relatorio_presenca(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
) -> str:
    """Gera o relatório de presença de um treinamento com totais e detalhes por status."""
    try:
        relatorio = await svc.relatorio_presenca(ctx.context.supabase, treinamento_id)
        return json.dumps(relatorio, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("relatorio_presenca falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao gerar relatório."}, ensure_ascii=False)


@function_tool
async def preview_ativacao_treinamento(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
    mensagem_customizada: str = "",
) -> str:
    """Mostra preview da mensagem de ativação/anúncio de um treinamento ANTES de enviar ao grupo geral.

    IMPORTANTE: Sempre chame esta ferramenta primeiro e apresente o preview para aprovação.
    """
    try:
        treinamento = await svc.buscar_treinamento(ctx.context.supabase, treinamento_id)
        if not treinamento:
            return json.dumps({"erro": f"Treinamento {treinamento_id} não encontrado."}, ensure_ascii=False)
        msg = _montar_msg_ativacao(treinamento, mensagem_customizada)
        grupo = ctx.context.agent_settings.get("whatsapp_grupo_geral") or "(não configurado)"
        return json.dumps(
            {
                "preview": True,
                "mensagem_exemplo": msg,
                "destinatario_grupo": grupo,
                "instrucao": "Confirme para ativar com a ferramenta 'ativar_treinamento'.",
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        logger.exception("preview_ativacao_treinamento falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao gerar preview de ativação."}, ensure_ascii=False)


@function_tool
async def ativar_treinamento(
    ctx: RunContextWrapper[AgentRunContext],
    treinamento_id: str,
    mensagem_customizada: str = "",
) -> str:
    """Ativa um treinamento enviando o anúncio ao grupo geral de WhatsApp.

    IMPORTANTE: Só chame após mostrar o preview (preview_ativacao_treinamento) e o usuário confirmar.
    """
    try:
        treinamento = await svc.buscar_treinamento(ctx.context.supabase, treinamento_id)
        if not treinamento:
            return json.dumps({"erro": f"Treinamento {treinamento_id} não encontrado."}, ensure_ascii=False)

        grupo = (ctx.context.agent_settings.get("whatsapp_grupo_geral") or "").strip()
        if not grupo:
            return json.dumps(
                {"erro": "Grupo geral de WhatsApp não configurado nas settings do agente (whatsapp_grupo_geral)."},
                ensure_ascii=False,
            )

        msg = _montar_msg_ativacao(treinamento, mensagem_customizada)
        ctx.context.pending_whatsapp_sends.append({"to_phone": grupo, "message": msg})

        try:
            await ctx.context.supabase.table("cronograma").update({"ativo": True}).eq("id", treinamento_id).execute()
        except Exception:
            logger.warning("Falha ao marcar treinamento como ativo id=%s", treinamento_id)

        return json.dumps(
            {"enviado": True, "grupo": grupo, "treinamento": treinamento.get("nome")},
            ensure_ascii=False,
        )
    except Exception:
        logger.exception("ativar_treinamento falhou id=%s", treinamento_id)
        return json.dumps({"erro": "Falha ao ativar o treinamento."}, ensure_ascii=False)


@function_tool
async def arquivar_registro_treinamento(
    ctx: RunContextWrapper[AgentRunContext],
    tabela: str,
    registro_id: str,
) -> str:
    """Arquiva (soft delete) um registro de treinamento. Tabelas permitidas: cronograma, inscricoes, unidades."""
    if tabela not in _TABELAS_PERMITIDAS:
        return json.dumps(
            {"erro": f"Tabela '{tabela}' não permitida. Use: {', '.join(sorted(_TABELAS_PERMITIDAS))}"},
            ensure_ascii=False,
        )
    try:
        ok = await svc.soft_delete(ctx.context.supabase, tabela, registro_id)
        return json.dumps({"arquivado": ok, "tabela": tabela, "id": registro_id}, ensure_ascii=False)
    except Exception:
        logger.exception("arquivar_registro_treinamento falhou tabela=%s id=%s", tabela, registro_id)
        return json.dumps({"erro": "Falha ao arquivar o registro."}, ensure_ascii=False)


@function_tool
async def reativar_registro_treinamento(
    ctx: RunContextWrapper[AgentRunContext],
    tabela: str,
    registro_id: str,
) -> str:
    """Reativa (undo soft delete) um registro de treinamento. Tabelas permitidas: cronograma, inscricoes, unidades."""
    if tabela not in _TABELAS_PERMITIDAS:
        return json.dumps(
            {"erro": f"Tabela '{tabela}' não permitida. Use: {', '.join(sorted(_TABELAS_PERMITIDAS))}"},
            ensure_ascii=False,
        )
    try:
        ok = await svc.soft_undelete(ctx.context.supabase, tabela, registro_id)
        return json.dumps({"reativado": ok, "tabela": tabela, "id": registro_id}, ensure_ascii=False)
    except Exception:
        logger.exception("reativar_registro_treinamento falhou tabela=%s id=%s", tabela, registro_id)
        return json.dumps({"erro": "Falha ao reativar o registro."}, ensure_ascii=False)


def create_treinamentos_capability(
    agent_id: str,
    agent_settings: dict[str, Any],
) -> Agent[AgentRunContext]:
    """Create the treinamentos specialist agent."""
    instructions = """Você é o especialista em *gestão de treinamentos* de uma rede de franquias de estética.

Seu fluxo de trabalho segue o padrão **Preview → Confirmar → Ação**:

1. **Antes de enviar qualquer mensagem WhatsApp**, sempre use a ferramenta de preview correspondente e apresente o resultado ao usuário para aprovação explícita.
2. **Só execute o envio real** após o usuário confirmar ("sim", "pode enviar", "confirmar", etc.).
3. Para consultas (cronograma, relatórios, detalhes), responda diretamente sem necessidade de preview.

Ferramentas disponíveis:
- `consultar_cronograma` — lista treinamentos (filtrável por mês)
- `detalhar_treinamento` — detalhes + inscrições de um treinamento
- `preview_confirmacao_presenca` — preview da mensagem de confirmação (USE PRIMEIRO)
- `enviar_confirmacao_presenca` — envia confirmações para unidades pendentes (SÓ APÓS PREVIEW)
- `relatorio_presenca` — relatório de presença por status
- `preview_ativacao_treinamento` — preview do anúncio de ativação (USE PRIMEIRO)
- `ativar_treinamento` — envia anúncio ao grupo geral (SÓ APÓS PREVIEW)
- `arquivar_registro_treinamento` — soft delete de registros
- `reativar_registro_treinamento` — desfaz soft delete

Responda sempre em português do Brasil. Seja objetivo e preciso."""

    return Agent(
        name="treinamentos",
        instructions=instructions,
        tools=[
            consultar_cronograma,
            detalhar_treinamento,
            preview_confirmacao_presenca,
            enviar_confirmacao_presenca,
            relatorio_presenca,
            preview_ativacao_treinamento,
            ativar_treinamento,
            arquivar_registro_treinamento,
            reativar_registro_treinamento,
        ],
        handoff_description=(
            "Especialista em treinamentos: cronograma, confirmações de presença, "
            "relatórios e ativação de treinamentos para a rede de franquias."
        ),
    )
