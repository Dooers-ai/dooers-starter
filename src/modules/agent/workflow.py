from __future__ import annotations

import logging
from typing import Any

from agents import Agent, Runner, trace

from dooers.agents.server import AgentIncoming, AgentMemory, AgentSend, format_user_input

from src.config import settings as app_settings
from src.modules.agent.agent_context import AgentRunContext
from src.modules.agent.capabilities.cortex import CORTEX_MAX_TURNS, create_cortex
from src.modules.agent.capabilities.guard import run_guard_check
from src.modules.agent.capabilities.treinamentos import create_treinamentos_capability
from src.modules.agent.capabilities.recrutamento import create_recrutamento_capability
from src.modules.helpers.llm_provider import (
    build_agents_run_config,
    litellm_api_key_env,
    resolve_agents_run_model_name,
)
from src.modules.services.supabase_client import get_supabase_client_for_settings

logger = logging.getLogger(__name__)


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
                "pending_whatsapp_sends": [],
            }

        reply_text, new_runner_items, pending_whatsapp_sends = await _execute_agent_workflow(
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
            pending_whatsapp_sends = []  # do not dispatch outbound if guard blocked

        return {
            "guard_in_ok": True,
            "guard_in_reason": "",
            "reply": reply_text,
            "guard_out_ok": guard_out_ok,
            "guard_out_reason": guard_out_reason if not guard_out_ok else "",
            "new_runner_items": new_runner_items,
            "pending_whatsapp_sends": pending_whatsapp_sends,
        }


async def _build_run_context(
    incoming: AgentIncoming,
    agent_settings: dict[str, Any],
) -> AgentRunContext:
    """Build AgentRunContext from incoming and agent_settings."""
    supabase = await get_supabase_client_for_settings(agent_settings)
    agent_id = incoming.context.agent_id or ""
    # channel_meta is set by whatsapp_channel.py → dispatch(..., channel_meta={...})
    channel_meta = getattr(incoming.context, "channel_meta", None) or {}
    whatsapp_meta = channel_meta.get("whatsapp", {}) if isinstance(channel_meta, dict) else {}
    whatsapp_instance_id = str(whatsapp_meta.get("instance_id") or "").strip()
    agent_phone_e164 = str(whatsapp_meta.get("agent_phone_e164") or "").strip()

    gestor_phone = (
        agent_settings.get("gestor_phone")
        or app_settings.gestor_phone
        or ""
    ).strip()

    link_avaliacao = (agent_settings.get("link_avaliacao_comportamental") or "").strip()
    nome_agente = (agent_settings.get("agent_name") or app_settings.assistant_name or "Assistente").strip()
    openai_api_key = (agent_settings.get("openai_api_key") or "").strip()

    return AgentRunContext(
        supabase=supabase,
        openai_api_key=openai_api_key,
        agent_id=agent_id,
        whatsapp_instance_id=whatsapp_instance_id,
        agent_phone_e164=agent_phone_e164,
        gestor_phone=gestor_phone,
        link_avaliacao_comportamental=link_avaliacao,
        nome_agente=nome_agente,
        agent_settings=agent_settings,
    )


async def _execute_agent_workflow(
    *,
    incoming: AgentIncoming,
    memory: AgentMemory,
    agent_settings: dict[str, Any],
    user_message_item: dict[str, Any],
    trace_group_id: str,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    agent_id = incoming.context.agent_id or ""

    run_context = await _build_run_context(incoming, agent_settings)

    treinamentos = create_treinamentos_capability(agent_id, agent_settings)
    recrutamento = create_recrutamento_capability(agent_id, agent_settings)

    cortex = await create_cortex(
        agent_id=agent_id,
        agent_settings=agent_settings,
        attach_knowledge_tools=False,
        knowledge_field_allowlist=None,
        extra_tools=None,
        handoffs=[treinamentos, recrutamento],
    )

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
                context=run_context,
            )
    except Exception:
        logger.exception("workflow _execute_agent_workflow: Runner.run failed")
        raise

    new_runner_items = _serialize_runner_new_items(result)
    pending_sends = list(run_context.pending_whatsapp_sends)

    out = result.final_output
    text = out if isinstance(out, str) else str(out) if out is not None else ""
    return text.strip(), new_runner_items, pending_sends
