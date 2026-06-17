"""Example domain capability: collect structured feedback via UI forms."""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, function_tool

FEEDBACK_KNOWLEDGE_FIELD_IDS = ("knowledge_files",)


@function_tool
def request_feedback_form() -> str:
    """Open a feedback form in the chat UI when the user wants to leave structured feedback."""
    return json.dumps({"requiresForm": True, "formType": "feedback"}, ensure_ascii=False)


async def create_feedback_capability(
    agent_id: str,
    agent_settings: dict[str, Any],
    *,
    rag_service: Any,
) -> Agent[Any]:
    """Specialist that hands back to cortex after collecting feedback context."""
    _ = agent_id
    tools: list[Any] = [request_feedback_form]
    rag_tools, _ = await rag_service.attach_file_search_tools(
        agent_id=agent_id,
        agent_settings=agent_settings,
        field_ids_allowlist=FEEDBACK_KNOWLEDGE_FIELD_IDS,
        max_num_results=6,
    )
    tools.extend(rag_tools)

    name = agent_settings.get("agent_name") or "Assistant"
    instructions = f"""You are the feedback specialist for {name}.

Your job:
- When the user wants to leave feedback, rate service, or report an issue, call **request_feedback_form**.
- After they submit the form, summarize what you received and thank them.
- Use knowledge search only for policy/FAQ context about how feedback is handled.
- Keep answers short and empathetic.
"""

    return Agent(
        name="feedback",
        instructions=instructions,
        tools=tools,
        handoff_description=(
            "Coleta feedback estruturado (nota, comentário) via formulário na UI. "
            "Use quando o utilizador quiser avaliar, reclamar ou sugerir melhorias."
        ),
    )
