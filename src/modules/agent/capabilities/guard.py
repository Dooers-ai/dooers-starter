"""Safety guardrails via OpenAI Agents SDK structured output."""

from __future__ import annotations

import logging
from typing import Any

from agents import Agent, Runner
from pydantic import BaseModel, Field

from src.modules.helpers.llm_provider import (
    build_agents_run_config,
    resolve_agents_run_model_name,
)

logger = logging.getLogger(__name__)


class GuardDecision(BaseModel):
    allowed: bool = Field(description="Whether the content passes configured policies.")
    reason: str = Field(
        default="",
        description="Short explanation in the same language as the text under review.",
    )


async def run_guard_check(
    *,
    phase: str,
    message_item: dict[str, Any],
    agent_settings: dict[str, Any],
) -> tuple[bool, str]:
    if not (agent_settings.get("guardrails_prompt") or "").strip():
        return True, ""

    policies = (agent_settings.get("guardrails_prompt") or "").strip()
    _provider, _logical, agents_model_id = resolve_agents_run_model_name(agent_settings)
    run_cfg = build_agents_run_config(agent_settings, agents_model_identifier=agents_model_id)

    guard_agent = Agent(
        name="guard_classifier",
        instructions=f"""You are a safety classifier. Apply ONLY the following policies:

{policies}

Evaluate the message for phase "{phase}" (user_request = incoming user message, assistant_reply = model answer).

For user_request with images: evaluate text and images together against the policies.

Respond using the structured output schema (allowed / reason).""",
        output_type=GuardDecision,
    )

    try:
        result = await Runner.run(
            guard_agent,
            [message_item],
            run_config=run_cfg,
            max_turns=4,
        )
    except Exception:
        logger.exception("Guard Runner.run failed")
        return False, "Não foi possível validar o conteúdo face às políticas configuradas."

    parsed = result.final_output
    if not isinstance(parsed, GuardDecision):
        logger.warning("Guard unexpected output type: %s", type(parsed).__name__)
        return False, "Não foi possível validar o conteúdo face às políticas configuradas."

    return parsed.allowed, (parsed.reason or "").strip()
