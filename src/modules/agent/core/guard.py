"""Input/output guardrails from the creator's Studio policies, via the Agents SDK.

When ``guardrails_prompt`` (or the input/output specific fields) is empty nothing runs. Otherwise a
small classifier agent judges the latest user message before the main run and the final reply
after it; a tripwire aborts the run and the handler shows the classifier's reason.
"""

from __future__ import annotations

import logging
from typing import Any

from agents import Agent, GuardrailFunctionOutput, Runner, input_guardrail, output_guardrail
from pydantic import BaseModel, Field

from src.modules.helpers.llm_provider import build_agents_run_config, resolve_agents_run_model_name

logger = logging.getLogger(__name__)
_VALIDATION_ERROR = "Não foi possível validar o conteúdo face às políticas configuradas."


class GuardDecision(BaseModel):
    allowed: bool = Field(description="Whether the content passes the configured policies.")
    reason: str = Field(default="", description="Short explanation in the same language as the reviewed text.")


async def run_guard_check(*, phase: str, message_item: Any, agent_settings: dict[str, Any], policies: str) -> tuple[bool, str]:
    policies = (policies or "").strip()
    if not policies:
        return True, ""
    model = resolve_agents_run_model_name(agent_settings)
    run_cfg = build_agents_run_config(agent_settings, model=model)
    classifier = Agent(
        name="guardClassifier",
        instructions=(
            "You are a safety classifier. Apply ONLY the policies below and return the structured decision.\n\n"
            f"Policies:\n{policies}\n\nPhase: {phase}. For user requests with images, evaluate text and images together."
        ),
        output_type=GuardDecision,
    )
    try:
        result = await Runner.run(classifier, [message_item], run_config=run_cfg, max_turns=3)
    except Exception:  # noqa: BLE001
        logger.exception("Guard classifier failed")
        return False, _VALIDATION_ERROR
    parsed = result.final_output
    if not isinstance(parsed, GuardDecision):
        return False, _VALIDATION_ERROR
    return parsed.allowed, (parsed.reason or "").strip()


def _latest_user_item(value: Any) -> Any:
    if isinstance(value, list):
        for item in reversed(value):
            if isinstance(item, dict) and item.get("role") == "user":
                return item
        return value[-1] if value else value
    return value


def _assistant_item(value: Any) -> dict[str, Any]:
    text = value if isinstance(value, str) else str(value) if value is not None else ""
    return {"role": "assistant", "content": text.strip() or "(sem conteúdo)"}


def _policies(agent_settings: dict[str, Any], field_id: str) -> str:
    return (agent_settings.get(field_id) or agent_settings.get("guardrails_prompt") or "").strip()


def build_guardrails(agent_settings: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    input_policies = _policies(agent_settings, "input_guardrails_prompt")
    output_policies = _policies(agent_settings, "output_guardrails_prompt")
    inputs: list[Any] = []
    outputs: list[Any] = []

    if input_policies:

        @input_guardrail
        async def configured_input_guardrail(ctx: Any, agent: Agent[Any], value: Any) -> GuardrailFunctionOutput:
            ok, reason = await run_guard_check(
                phase="user_request", message_item=_latest_user_item(value), agent_settings=agent_settings, policies=input_policies
            )
            return GuardrailFunctionOutput(output_info=reason, tripwire_triggered=not ok)

        inputs.append(configured_input_guardrail)

    if output_policies:

        @output_guardrail
        async def configured_output_guardrail(ctx: Any, agent: Agent[Any], value: Any) -> GuardrailFunctionOutput:
            ok, reason = await run_guard_check(
                phase="assistant_reply", message_item=_assistant_item(value), agent_settings=agent_settings, policies=output_policies
            )
            return GuardrailFunctionOutput(output_info=reason, tripwire_triggered=not ok)

        outputs.append(configured_output_guardrail)

    return inputs, outputs


def reason_from_guardrail_exception(exc: BaseException) -> str:
    result = getattr(exc, "guardrail_result", None) or getattr(exc, "result", None)
    output = getattr(result, "output", None) if result is not None else None
    info = getattr(output, "output_info", None)
    if isinstance(info, GuardDecision):
        return (info.reason or "").strip()
    if isinstance(info, str):
        return info.strip()
    if isinstance(info, dict):
        return str(info.get("reason") or info.get("message") or "").strip()
    return ""
