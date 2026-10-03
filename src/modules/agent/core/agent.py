from __future__ import annotations

from typing import Any

from agents import Agent

from src.modules.agent.core.context import RuntimeContext
from src.modules.agent.core.guard import build_guardrails
from src.modules.agent.core.policies import build_static_instructions
from src.modules.agent.core.tools import ALL_TOOLS

MAX_TURNS = 16


def build_agent(agent_settings: dict[str, Any]) -> Agent[RuntimeContext]:
    """One customer-facing agent with a stable tool surface. Specialization comes from Skills."""
    input_guardrails, output_guardrails = build_guardrails(agent_settings)
    return Agent[RuntimeContext](
        name=str(agent_settings.get("agent_name") or "Agent").strip() or "Agent",
        instructions=build_static_instructions(agent_settings),
        tools=list(ALL_TOOLS),
        input_guardrails=input_guardrails,
        output_guardrails=output_guardrails,
    )
