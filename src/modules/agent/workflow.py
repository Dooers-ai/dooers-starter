from __future__ import annotations

import logging
from typing import Any

from agents import Agent, Runner, trace

from dooers.agents.server import AgentIncoming, AgentMemory, AgentSend, format_user_input

from src.config import settings as app_settings
from src.modules.agent.capabilities.cortex import CORTEX_MAX_TURNS, create_cortex
from src.modules.agent.capabilities.feedback import create_feedback_capability
from src.modules.agent.capabilities.guard import run_guard_check
from src.modules.rag.service import rag_service
from src.modules.helpers.llm_provider import (
    build_agents_run_config,
    litellm_api_key_env,
    resolve_agents_run_model_name,
)

logger = logging.getLogger(__name__)


async def _create_additional_capabilities(agent_id: str, agent_settings: dict[str, Any]) -> list[Agent[Any]]:
    feedback = await create_feedback_capability(
        agent_id,
        agent_settings,
        rag_service=rag_service,
    )
    return [feedback]


def _serialize_runner_new_items(result: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    new_items = getattr(result, "new_items", None) or []
    for item in new_items:
        raw = getattr(item, "raw_item", None)
        if raw is None:
            continue
        if hasattr(raw, "model_dump"):
            out.append(raw.model_dump())
        elif isinstance(raw, dict):
            out.append(raw)
    return out


async def run_workflow(
    *,
    incoming: AgentIncoming,
    send: AgentSend,
    memory: AgentMemory,
    analytics: Any,
    agent_settings: dict[str, Any],
    api_provider: str,
) -> dict[str, Any]:
    """Guard-in → agent graph → guard-out."""
    logger.debug("run_workflow thread=%s send=%s", incoming.context.thread_id, type(send).__name__)
    trace_group_id = f"thread:{incoming.context.thread_id}"

    async with litellm_api_key_env(agent_settings):
        agent_id = incoming.context.agent_id or ""
        await analytics.track("llm.request", data={"agent_id": agent_id})

        user_message_item = format_user_input(incoming, api_provider, strict=True)

        guard_in_ok, guard_in_reason = await run_guard_check(
            phase="user_request",
            message_item=user_message_item,
            agent_settings=agent_settings,
        )

        if not guard_in_ok:
            logger.info("Guard-in blocked: %s", (guard_in_reason or "")[:200])
            reply = guard_in_reason or "A mensagem não pode ser processada."
            return {
                "guard_in_ok": False,
                "guard_in_reason": guard_in_reason,
                "reply": reply,
                "guard_out_ok": False,
                "guard_out_reason": "",
                "new_runner_items": [],
            }

        reply_text, new_runner_items = await _execute_agent_workflow(
            incoming=incoming,
            memory=memory,
            agent_settings=agent_settings,
            user_message_item=user_message_item,
            trace_group_id=trace_group_id,
        )

        guard_out_ok, guard_out_reason = await run_guard_check(
            phase="assistant_reply",
            message_item={
                "type": "message",
                "role": "assistant",
                "content": (reply_text or "").strip() or "(sem conteúdo)",
            },
            agent_settings=agent_settings,
        )

        if not guard_out_ok:
            logger.info("Guard-out blocked: %s", (guard_out_reason or "")[:200])
            reply_text = guard_out_reason or "A resposta não pôde ser enviada."

        return {
            "guard_in_ok": True,
            "guard_in_reason": "",
            "reply": reply_text,
            "guard_out_ok": guard_out_ok,
            "guard_out_reason": guard_out_reason if not guard_out_ok else "",
            "new_runner_items": new_runner_items,
        }


async def _execute_agent_workflow(
    *,
    incoming: AgentIncoming,
    memory: AgentMemory,
    agent_settings: dict[str, Any],
    user_message_item: dict[str, Any],
    trace_group_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    agent_id = incoming.context.agent_id or ""
    capability_agents = await _create_additional_capabilities(agent_id, agent_settings)

    cortex = await create_cortex(
        agent_id=agent_id,
        agent_settings=agent_settings,
        attach_knowledge_tools=True,
        knowledge_field_allowlist=None,
        extra_tools=None,
        handoffs=None,
    )
    for agent in capability_agents:
        cortex.handoffs.append(agent)

    starting_capability: Agent[Any] = cortex

    _, _, agents_model_id = resolve_agents_run_model_name(agent_settings)
    run_config = build_agents_run_config(agent_settings, agents_model_identifier=agents_model_id)

    history = await memory.get_history(limit=30, format="openai_responses")
    input_items: list[Any] = list(history)
    input_items.append(user_message_item)

    workflow_trace_name = app_settings.api_agent_name

    try:
        with trace(workflow_trace_name, group_id=trace_group_id):
            result = await Runner.run(
                starting_capability,
                input_items,
                run_config=run_config,
                max_turns=CORTEX_MAX_TURNS,
                context=None,
            )
    except Exception:
        logger.exception("workflow _execute_agent_workflow: Runner.run failed")
        raise

    new_runner_items = _serialize_runner_new_items(result)

    out = result.final_output
    text = out if isinstance(out, str) else str(out) if out is not None else ""
    return text.strip(), new_runner_items
