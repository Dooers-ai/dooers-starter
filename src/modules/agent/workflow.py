"""One user turn: build the Runner input, stream the agent, repair passive replies.

Yields UI events (``send.reasoning`` / ``send.tool_call`` / ``send.tool_result``) while the agent
works and finishes with a :class:`WorkflowOutcome`. The handler in ``agent.py`` decides how to
present the outcome (text, voice, failure codes).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agents import (
    InputGuardrailTripwireTriggered,
    ItemHelpers,
    MessageOutputItem,
    OutputGuardrailTripwireTriggered,
    ReasoningItem,
    RunItemStreamEvent,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    trace,
)
from dooers.agents.server import AgentIncoming, AgentMemory, AgentSend, format_user_input

from src.config import settings as app_settings
from src.modules.agent.core.agent import MAX_TURNS, build_agent
from src.modules.agent.core.context import RuntimeContext
from src.modules.agent.core.execution_guard import (
    SAFE_FAILURE_REPLY,
    is_passive_deferred_action,
    repair_instruction,
)
from src.modules.agent.core.guard import reason_from_guardrail_exception
from src.modules.doc_processing.repository import list_thread_documents
from src.modules.helpers.llm_provider import (
    build_agents_run_config,
    resolve_agents_run_model_name,
    resolve_agents_wire_format,
)
from src.modules.rag.service import rag_service

logger = logging.getLogger(__name__)

CACHE_SHARDS = 16
HISTORY_LIMIT = 30
REPAIR_MAX_TURNS = 8

_TOOL_DISPLAY = {
    "load_skill": "Carregando skill",
    "search_knowledge": "Consultando base de conhecimento",
    "get_thread_document_context": "Lendo documentos da conversa",
    "calculate": "Calculando",
}


@dataclass
class WorkflowOutcome:
    reply: str
    status: str = "ok"  # ok | guard_input | guard_output | passive_failure
    reason: str = ""
    model: str = ""
    tools_called: list[str] = field(default_factory=list)
    skills_loaded: list[str] = field(default_factory=list)


def prompt_cache_key(agent_id: str, thread_id: str) -> str:
    """Stable per agent, sharded by thread so one hot agent does not pin a single cache slot."""
    shard = int.from_bytes(hashlib.sha256(thread_id.encode("utf-8")).digest()[:2], "big") % CACHE_SHARDS
    return f"starter:v1:{agent_id}:shard-{shard}"


def tool_display_name(name: str) -> str:
    return _TOOL_DISPLAY.get(name, name.replace("_", " ").capitalize())


def _parse_args(raw: Any) -> dict[str, Any]:
    args = getattr(raw, "arguments", None)
    if isinstance(args, dict):
        return args
    if isinstance(args, str) and args.strip():
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": args[:500]}
    return {}


def _summarize_output(output: Any, *, limit: int = 1200) -> Any:
    text = json.dumps(output, ensure_ascii=False, default=str) if isinstance(output, (dict, list)) else str(output or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _reasoning_text(item: ReasoningItem) -> str:
    raw = item.raw_item
    chunks: list[str] = []
    for block in getattr(raw, "summary", None) or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(str(text))
    for block in getattr(raw, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(str(text))
    return "\n".join(chunks).strip()


async def _current_event_already_persisted(*, incoming: AgentIncoming, memory: AgentMemory) -> bool:
    event_id = getattr(incoming.context, "event_id", None)
    if not event_id:
        return False
    try:
        recent = await memory.get_history_raw(limit=5, order="desc")
    except Exception:  # noqa: BLE001
        logger.exception("Could not inspect recent events")
        return False
    return any(getattr(e, "id", None) == event_id and getattr(e, "type", None) == "message" for e in recent)


async def _stream_run(
    *, agent, input_items: list[Any], run_config, runtime: RuntimeContext, send: AgentSend, author: str, max_turns: int
) -> AsyncIterator[Any]:
    """Run once, yielding UI events; the final yield is the Runner result."""
    streamed = Runner.run_streamed(agent, input_items, run_config=run_config, max_turns=max_turns, context=runtime)
    pending: dict[str, tuple[str, dict[str, Any]]] = {}
    seen_reasoning: set[str] = set()
    async for event in streamed.stream_events():
        if not isinstance(event, RunItemStreamEvent):
            continue
        item = event.item
        if isinstance(item, ReasoningItem):
            text = _reasoning_text(item)
            if text and text not in seen_reasoning:
                seen_reasoning.add(text)
                yield send.reasoning(text, author=author)
        elif isinstance(item, ToolCallItem):
            raw = item.raw_item
            name = str(getattr(raw, "name", None) or "tool")
            call_id = str(getattr(raw, "call_id", None) or getattr(raw, "id", None) or "")
            args = _parse_args(raw)
            pending[call_id] = (name, args)
            yield send.tool_call(name, args, display_name=tool_display_name(name), id=call_id or None)
        elif isinstance(item, ToolCallOutputItem):
            raw = item.raw_item
            call_id = str(raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", "") or "")
            name, args = pending.pop(call_id, ("tool", {}))
            yield send.tool_result(
                name, _summarize_output(item.output), args=args, display_name=tool_display_name(name), id=call_id or None
            )
        elif isinstance(item, MessageOutputItem):
            # Final text is emitted by the handler once (after the execution guard), not streamed.
            ItemHelpers.text_message_output(item)
    yield streamed


async def run_workflow(
    *,
    incoming: AgentIncoming,
    send: AgentSend,
    memory: AgentMemory,
    analytics: Any,
    agent_settings: dict[str, Any],
    author: str,
) -> AsyncIterator[Any]:
    agent_id = incoming.context.agent_id or ""
    thread_id = incoming.context.thread_id
    wire = resolve_agents_wire_format()
    model = resolve_agents_run_model_name(agent_settings)
    user_item = format_user_input(incoming, wire, strict=True)

    thread_documents = await list_thread_documents(memory=memory, agent_id=agent_id, thread_id=thread_id)
    history = list(await memory.get_history(limit=HISTORY_LIMIT, format=wire))  # type: ignore[arg-type]
    runtime = RuntimeContext.from_history(
        agent_id=agent_id,
        thread_id=thread_id,
        event_id=getattr(incoming.context, "event_id", None),
        agent_settings=agent_settings,
        history_items=history,
        organization_id=incoming.context.organization_id or "",
        workspace_id=incoming.context.workspace_id or "",
        user_id=incoming.context.user.user_id or "",
        user_name=incoming.context.user.user_name or "",
        channel=incoming.context.channel or "",
        knowledge_bases=rag_service.knowledge_bases_for(agent_settings),
        thread_documents=thread_documents,
    )
    agent = build_agent(agent_settings)
    run_config = build_agents_run_config(agent_settings, model=model, prompt_cache_key=prompt_cache_key(agent_id, thread_id))

    input_items: list[Any] = [*history, {"role": "system", "content": runtime.state_message()}]
    has_live_content = any(hasattr(p, "type") for p in (incoming.content or []))
    if has_live_content or not await _current_event_already_persisted(incoming=incoming, memory=memory):
        input_items.append(user_item)

    logger.info("turn thread=%s model=%s wire=%s skills=%d docs=%d", thread_id, model, wire, len(runtime.skills), len(thread_documents))
    await analytics.track("llm.request", data={"agent_id": agent_id, "model": model, "wire": wire})

    outcome = WorkflowOutcome(reply="", model=model)
    try:
        with trace(app_settings.api_agent_name, group_id=f"thread:{thread_id}"):
            result = None
            async for ev in _stream_run(
                agent=agent, input_items=input_items, run_config=run_config, runtime=runtime, send=send, author=author, max_turns=MAX_TURNS
            ):
                result = ev
                if not hasattr(ev, "final_output"):
                    yield ev
            reply = _final_text(result)

            if is_passive_deferred_action(reply):
                logger.warning("Passive reply; repairing thread=%s reply=%r", thread_id, reply[:160])
                continuation = result.to_input_list()
                continuation.append({"role": "system", "content": repair_instruction()})
                async for ev in _stream_run(
                    agent=agent,
                    input_items=continuation,
                    run_config=run_config,
                    runtime=runtime,
                    send=send,
                    author=author,
                    max_turns=REPAIR_MAX_TURNS,
                ):
                    result = ev
                    if not hasattr(ev, "final_output"):
                        yield ev
                reply = _final_text(result)
                if is_passive_deferred_action(reply):
                    reply, outcome.status = SAFE_FAILURE_REPLY, "passive_failure"
    except InputGuardrailTripwireTriggered as exc:
        outcome.status, outcome.reason = "guard_input", reason_from_guardrail_exception(exc)
        reply = outcome.reason or "A mensagem não pode ser processada pelas políticas configuradas."
    except OutputGuardrailTripwireTriggered as exc:
        outcome.status, outcome.reason = "guard_output", reason_from_guardrail_exception(exc)
        reply = outcome.reason or "A resposta não pôde ser enviada pelas políticas configuradas."

    outcome.reply = reply
    outcome.tools_called = list(runtime.tools_called)
    outcome.skills_loaded = sorted(runtime.loaded_skills)
    yield outcome


def _final_text(result: Any) -> str:
    out = getattr(result, "final_output", None)
    return (out if isinstance(out, str) else str(out) if out is not None else "").strip()
