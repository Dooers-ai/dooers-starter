"""Tool implementations. Each one records itself in the RuntimeContext for telemetry.

Add domain tools here (ERP lookups, bookings, tickets…). Keep the model-facing function thin:
validate arguments, call a business module that returns a plain result, format a compact string.
Business errors are returned as text so the model can recover; never raise for expected failures.
"""

from __future__ import annotations

import ast
import json
import logging
import math
import operator
from typing import Any

from agents import RunContextWrapper, function_tool

from src.modules.agent.core.context import RuntimeContext
from src.modules.agent.core.skills import find_skill, load_skill_reply
from src.modules.doc_processing.search import render_document_context
from src.modules.rag.managed import rebind_execution_context
from src.modules.rag.service import rag_service

logger = logging.getLogger(__name__)


@function_tool
async def load_skill(ctx: RunContextWrapper[RuntimeContext], skill: str) -> str:
    """Load the complete instructions of a configured Skill by id, name or filename."""
    ctx.context.record_tool_call("load_skill")
    spec = find_skill(ctx.context.skills, skill)
    if spec is None:
        known = ", ".join(row.id for row in ctx.context.skills) or "none"
        return f"Skill not found: {skill!r}. Available Skill ids: {known}."
    ctx.context.load_skill(spec.id)
    return load_skill_reply(spec)


@function_tool
async def search_knowledge(ctx: RunContextWrapper[RuntimeContext], query: str, max_results: int = 8) -> str:
    """Search the agent's private knowledge bases for passages relevant to the query."""
    ctx.context.record_tool_call("search_knowledge")
    clean = (query or "").strip()
    if not clean:
        return "Knowledge query is empty."
    if not rag_service.enabled:
        return "No knowledge base is configured for this agent."
    if not ctx.context.knowledge_bases:
        return "The knowledge base has no documents yet."
    # Tool calls run in child tasks; the managed RAG context is task-scoped.
    rebind_execution_context(
        agent_id=ctx.context.agent_id,
        organization_id=ctx.context.organization_id,
        workspace_id=ctx.context.workspace_id,
        user_id=ctx.context.user_id,
        channel=ctx.context.channel,
    )
    try:
        result = await rag_service.search(
            query=clean,
            knowledge_bases=ctx.context.knowledge_bases,
            max_results=max(1, min(20, int(max_results or 8))),
        )
    except Exception as exc:  # noqa: BLE001 — surface to the model, keep the turn alive
        logger.exception("search_knowledge failed")
        return f"Knowledge search failed ({type(exc).__name__}). Answer from what you know and say the search failed."
    return result or "No relevant passages were found in the knowledge base."


@function_tool
async def get_thread_document_context(
    ctx: RunContextWrapper[RuntimeContext],
    query: str,
    document_id: str | None = None,
    mode: str = "search",
) -> str:
    """Read or search documents attached to this conversation. mode: search | full | summary."""
    ctx.context.record_tool_call("get_thread_document_context")
    return render_document_context(ctx.context.thread_documents, query=query or "", document_id=document_id, mode=mode)


_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS: dict[type[ast.unaryop], Any] = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(float(right)) > 100:
            raise ValueError("Exponent too large")
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords:
            raise ValueError("Keyword arguments are not supported")
        return _FUNCTIONS[node.func.id](*[_safe_eval(arg) for arg in node.args])
    raise ValueError("Unsupported expression")


def evaluate_expression(expression: str) -> dict[str, Any]:
    clean = (expression or "").strip()
    if not clean or len(clean) > 500:
        return {"expression": clean, "error": "Invalid or empty expression."}
    try:
        value = _safe_eval(ast.parse(clean, mode="eval"))
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError("Non-finite result")
        return {"expression": clean, "result": value}
    except Exception as exc:  # noqa: BLE001
        return {"expression": clean, "error": str(exc)}


@function_tool
def calculate(ctx: RunContextWrapper[RuntimeContext], expression: str) -> str:
    """Evaluate arithmetic (+ - * / // % **, abs, round, sqrt, log, min, max, pi, e)."""
    ctx.context.record_tool_call("calculate")
    return json.dumps(evaluate_expression(expression), ensure_ascii=False)


ALL_TOOLS = [load_skill, search_knowledge, get_thread_document_context, calculate]
