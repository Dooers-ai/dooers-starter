"""Recruitment capability — 6 tools for the franchise recruitment workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from agents import Agent, RunContextWrapper, function_tool

from src.modules.agent.agent_context import AgentRunContext
from src.modules.services import recrutamento_service as svc

logger = logging.getLogger(__name__)


def _montar_msg_contato(candidato: dict, vaga: dict, link_avaliacao: str = "") -> str:
    """Build WhatsApp first-contact message for a candidate."""
    nome = candidato.get("nome") or "Candidato"
    titulo_vaga = vaga.get("titulo") or "nossa vaga"

    linhas = [
        f"Olá, *{nome}*! 👋",
        "",
        f"Identificamos seu currículo para a vaga de *{titulo_vaga}* em nossa rede de franquias de estética.",
        "",
        "Ficamos muito interessados no seu perfil e gostaríamos de avançar no processo seletivo.",
    ]

    if link_avaliacao:
        linhas += [
            "",
            "Como próximo passo, pedimos que preencha nossa avaliação comportamental:",
            f"🔗 {link_avaliacao}",
            "",
            "O formulário leva cerca de 5 minutos e nos ajuda a entender melhor seu perfil.",
        ]

    linhas += [
        "",
        "Ficamos à disposição para qualquer dúvida. Aguardamos seu retorno!",
    ]

    return "\n".join(linhas)


@function_tool
async def listar_vagas(
    ctx: RunContextWrapper[AgentRunContext],
    apenas_ativas: bool = True,
) -> str:
    """Lista as vagas disponíveis. Use apenas_ativas=False para incluir vagas inativas."""
    try:
        vagas = await svc.listar_vagas(ctx.context.supabase, apenas_ativas=apenas_ativas)
        if not vagas:
            return json.dumps({"vagas": [], "mensagem": "Nenhuma vaga encontrada."}, ensure_ascii=False)
        return json.dumps({"vagas": vagas}, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("listar_vagas falhou")
        return json.dumps({"erro": "Falha ao listar vagas."}, ensure_ascii=False)


@function_tool
async def listar_candidatos(
    ctx: RunContextWrapper[AgentRunContext],
    vaga_id: str,
    status: str = "",
) -> str:
    """Lista candidatos de uma vaga, ordenados por nota (maior primeiro). Use status para filtrar (ex: 'analisado', 'contatado')."""
    try:
        candidatos = await svc.listar_candidatos(ctx.context.supabase, vaga_id, status=status)
        if not candidatos:
            return json.dumps(
                {"candidatos": [], "mensagem": "Nenhum candidato encontrado para esta vaga."},
                ensure_ascii=False,
            )
        return json.dumps({"candidatos": candidatos, "total": len(candidatos)}, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("listar_candidatos falhou vaga_id=%s", vaga_id)
        return json.dumps({"erro": "Falha ao listar candidatos."}, ensure_ascii=False)


@function_tool
async def detalhar_candidato(
    ctx: RunContextWrapper[AgentRunContext],
    candidato_id: str,
) -> str:
    """Retorna detalhes completos de um candidato. Dispara análise de currículo via GPT-4o se ainda não foi feita."""
    try:
        candidato = await svc.buscar_candidato(ctx.context.supabase, candidato_id)
        if not candidato:
            return json.dumps({"erro": f"Candidato {candidato_id} não encontrado."}, ensure_ascii=False)

        # Trigger PDF analysis if not done yet
        if candidato.get("nota") is None and candidato.get("pdf_url"):
            candidato = await svc.garantir_analise_pdf(
                ctx.context.supabase,
                candidato,
                ctx.context.openai_api_key,
            )

        return json.dumps({"candidato": candidato}, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("detalhar_candidato falhou id=%s", candidato_id)
        return json.dumps({"erro": "Falha ao detalhar candidato."}, ensure_ascii=False)


@function_tool
async def ranking_candidatos(
    ctx: RunContextWrapper[AgentRunContext],
    vaga_id: str,
) -> str:
    """Retorna o ranking dos candidatos de uma vaga com nota e justificativa. Candidatos sem nota aparecem por último."""
    try:
        candidatos = await svc.listar_candidatos(ctx.context.supabase, vaga_id)
        if not candidatos:
            return json.dumps(
                {"ranking": [], "mensagem": "Nenhum candidato para esta vaga."},
                ensure_ascii=False,
            )

        ranking = [
            {
                "posicao": idx + 1,
                "id": c.get("id"),
                "nome": c.get("nome"),
                "email": c.get("email"),
                "telefone": c.get("telefone"),
                "nota": c.get("nota"),
                "justificativa": c.get("justificativa"),
                "status": c.get("status"),
            }
            for idx, c in enumerate(candidatos)
        ]

        return json.dumps(
            {"ranking": ranking, "total": len(ranking), "vaga_id": vaga_id},
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        logger.exception("ranking_candidatos falhou vaga_id=%s", vaga_id)
        return json.dumps({"erro": "Falha ao gerar ranking."}, ensure_ascii=False)


@function_tool
async def preview_contato_candidato(
    ctx: RunContextWrapper[AgentRunContext],
    candidato_id: str,
) -> str:
    """Mostra preview da mensagem de contato de um candidato ANTES de enviar.

    IMPORTANTE: Sempre chame esta ferramenta primeiro e apresente o preview ao usuário para aprovação.
    Só envie após confirmação explícita do usuário.
    """
    try:
        candidato = await svc.buscar_candidato(ctx.context.supabase, candidato_id)
        if not candidato:
            return json.dumps({"erro": f"Candidato {candidato_id} não encontrado."}, ensure_ascii=False)

        vaga = candidato.get("vagas") or {}
        link_avaliacao = ctx.context.link_avaliacao_comportamental or ""
        msg = _montar_msg_contato(candidato, vaga, link_avaliacao)
        telefone = (candidato.get("telefone") or "").strip()

        return json.dumps(
            {
                "preview": True,
                "mensagem_exemplo": msg,
                "destinatario": {
                    "nome": candidato.get("nome"),
                    "telefone": telefone or "(não informado)",
                },
                "instrucao": "Confirme para enviar com a ferramenta 'contatar_candidato'.",
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        logger.exception("preview_contato_candidato falhou id=%s", candidato_id)
        return json.dumps({"erro": "Falha ao gerar preview de contato."}, ensure_ascii=False)


@function_tool
async def contatar_candidato(
    ctx: RunContextWrapper[AgentRunContext],
    candidato_id: str,
) -> str:
    """Envia mensagem de contato ao candidato via WhatsApp e marca como 'contatado' atomicamente.

    IMPORTANTE: Só chame após mostrar o preview (preview_contato_candidato) e o usuário confirmar.
    Usa atualização atômica para evitar duplo contato.
    """
    try:
        candidato = await svc.buscar_candidato(ctx.context.supabase, candidato_id)
        if not candidato:
            return json.dumps({"erro": f"Candidato {candidato_id} não encontrado."}, ensure_ascii=False)

        telefone = (candidato.get("telefone") or "").strip()
        if not telefone:
            return json.dumps(
                {"erro": "Candidato não possui telefone cadastrado."},
                ensure_ascii=False,
            )

        vaga = candidato.get("vagas") or {}
        link_avaliacao = ctx.context.link_avaliacao_comportamental or ""
        msg = _montar_msg_contato(candidato, vaga, link_avaliacao)

        # Atomically mark as contacted to prevent duplicates
        marcado = await svc.contatar_candidato_atomico(ctx.context.supabase, candidato_id)
        if not marcado:
            return json.dumps(
                {"aviso": "Candidato já foi contatado anteriormente.", "enviado": False},
                ensure_ascii=False,
            )

        ctx.context.pending_whatsapp_sends.append({"to_phone": telefone, "message": msg})

        return json.dumps(
            {
                "enviado": True,
                "candidato": candidato.get("nome"),
                "telefone": telefone,
                "vaga": vaga.get("titulo"),
            },
            ensure_ascii=False,
        )
    except Exception:
        logger.exception("contatar_candidato falhou id=%s", candidato_id)
        return json.dumps({"erro": "Falha ao contatar candidato."}, ensure_ascii=False)


def create_recrutamento_capability(
    agent_id: str,
    agent_settings: dict[str, Any],
) -> Agent[AgentRunContext]:
    """Create the recrutamento specialist agent."""
    instructions = """Você é o especialista em *recrutamento* de uma rede de franquias de estética.

Seu fluxo de trabalho segue o padrão **Preview → Confirmar → Ação**:

1. **Antes de contatar qualquer candidato via WhatsApp**, sempre use `preview_contato_candidato` e apresente o resultado ao usuário para aprovação explícita.
2. **Só execute o envio real** após o usuário confirmar ("sim", "pode enviar", "confirmar", etc.).
3. Para consultas (vagas, candidatos, rankings), responda diretamente sem necessidade de preview.

Ferramentas disponíveis:
- `listar_vagas` — lista vagas abertas (ou todas se apenas_ativas=False)
- `listar_candidatos` — candidatos de uma vaga, opcionalmente filtrados por status
- `detalhar_candidato` — detalhes do candidato + análise GPT-4o do currículo se ainda não feita
- `ranking_candidatos` — ranking por nota (0-10) com justificativa
- `preview_contato_candidato` — preview da mensagem de contato (USE PRIMEIRO)
- `contatar_candidato` — envia mensagem e marca como contatado atomicamente (SÓ APÓS PREVIEW)

Sobre a análise de currículos:
- A nota vai de 0 a 10 e reflete adequação ao setor de estética/beleza.
- `detalhar_candidato` dispara a análise automaticamente se o PDF não foi analisado.
- Candidatos sem nota aparecem por último no ranking.

Responda sempre em português do Brasil. Seja objetivo e preciso."""

    return Agent(
        name="recrutamento",
        instructions=instructions,
        tools=[
            listar_vagas,
            listar_candidatos,
            detalhar_candidato,
            ranking_candidatos,
            preview_contato_candidato,
            contatar_candidato,
        ],
        handoff_description=(
            "Especialista em recrutamento: vagas abertas, pipeline de candidatos, "
            "análise de currículos via IA e contato via WhatsApp."
        ),
    )
