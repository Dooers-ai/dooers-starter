"""Cortex capability: central orchestrator Agent for franchise training and recruitment."""

from __future__ import annotations

from typing import Any

from agents import Agent

from src.config import settings as app_settings

CORTEX_MAX_TURNS = 12


def _build_cortex_system_prompt(agent_settings: dict[str, Any]) -> str:
    name = agent_settings.get("agent_name") or app_settings.assistant_name or "Assistente"
    base = agent_settings.get("system_prompt") or ""
    parts = [
        f"Você é {name}, assistente operacional de uma rede de franquias do setor de estética.",
        "Você gerencia dois processos críticos via WhatsApp:",
        "1. TREINAMENTOS: cronograma, confirmações de presença e relatórios — encaminhe para o especialista 'treinamentos'.",
        "2. RECRUTAMENTO: triagem de currículos, pipeline de candidatos e contato — encaminhe para o especialista 'recrutamento'.",
        "Responda sempre em português do Brasil. Seja direto e objetivo.",
    ]
    if base:
        parts.append(base)
    return "\n\n".join(parts)


async def create_cortex(
    agent_id: str,
    agent_settings: dict[str, Any],
    *,
    attach_knowledge_tools: bool = False,
    knowledge_field_allowlist: Any = None,
    extra_tools: list[Any] | None = None,
    handoffs: list[Any] | None = None,
) -> Agent[Any]:
    # This agent does not use RAG — attach_knowledge_tools is always False
    tools: list[Any] = list(extra_tools or [])

    system = _build_cortex_system_prompt(agent_settings)

    agent = Agent(
        name="cortex",
        instructions=system,
        tools=tools,
        handoff_description=(
            "Agente central: recebe mensagem do utilizador, "
            "identifica o domínio (treinamentos ou recrutamento) e encaminha para o especialista correto."
        ),
    )
    if handoffs:
        agent.handoffs.extend(handoffs)
    return agent
