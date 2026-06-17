"""Cortex capability: central ``Agent`` with optional RAG tools."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agents import Agent

from src.config import settings as app_settings
from src.modules.rag.service import rag_service

CORTEX_MAX_TURNS = 12


def _build_cortex_system_prompt(agent_settings: dict[str, Any]) -> str:
    name = agent_settings.get("agent_name") or app_settings.assistant_name
    persona = agent_settings.get("persona") or "A helpful assistant."
    company = agent_settings.get("company_name") or ""
    base = agent_settings.get("system_prompt") or "You help users accurately and concisely."

    parts = [
        f"You are {name}.",
        f"Persona and role: {persona}.",
    ]
    if company:
        parts.append(f"Company context: {company}.")
    parts.append(base)
    return "\n\n".join(parts)


def _knowledge_instructions(*, enable_tool: bool, tool_name: str) -> str:
    if enable_tool:
        return (
            f"A «Base de Conhecimento» está configurada. Use a ferramenta **{tool_name}** "
            "quando a resposta deva fundamentar-se em documentos carregados pelo utilizador. "
            "Envie uma consulta curta e específica. Não invente factos não "
            "suportados pelos extratos devolvidos; se não houver resultados úteis, diga-o claramente."
        )
    return (
        "Não há base de conhecimento configurada neste agente para pesquisa documental — responda com "
        "o contexto da conversação e bom senso."
    )


async def create_cortex(
    agent_id: str,
    agent_settings: dict[str, Any],
    *,
    attach_knowledge_tools: bool = False,
    knowledge_field_allowlist: Iterable[str] | None = None,
    extra_tools: list[Any] | None = None,
    handoffs: list[Any] | None = None,
) -> Agent[Any]:
    tools: list[Any] = list(extra_tools or [])
    knowledge_hint = "dooers_file_search_*"
    kb_enabled = False

    if attach_knowledge_tools:
        rag_tools, knowledge_hint = await rag_service.attach_file_search_tools(
            agent_id=agent_id,
            agent_settings=agent_settings,
            field_ids_allowlist=knowledge_field_allowlist,
            max_num_results=None,
        )
        tools.extend(rag_tools)
        kb_enabled = bool(rag_tools)

    system = _build_cortex_system_prompt(agent_settings)
    system = (
        f"{system}\n\n{_knowledge_instructions(enable_tool=kb_enabled, tool_name=knowledge_hint)}"
    )

    agent = Agent(
        name="cortex",
        instructions=system,
        tools=tools,
        handoff_description="Agente central: mensagem do utilizador, ferramentas (incl. RAG se existir), depois resposta.",
    )
    if handoffs:
        agent.handoffs.extend(handoffs)
    return agent
