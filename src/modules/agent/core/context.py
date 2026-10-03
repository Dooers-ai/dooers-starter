"""Per-turn trusted state. Nothing here is written by the model.

The static prompt (``policies.py``) must not change between turns of the same agent version, so
anything volatile — date, channel, who is talking, which documents exist, which Skills are
already loaded — goes into ``state_message()`` and is appended as the last system message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.modules.agent.core.skills import SkillSpec, compile_skills, loaded_skill_ids_from_text
from src.modules.doc_processing.models import ProcessedDocument
from src.modules.doc_processing.prompt_context import build_document_manifest


@dataclass
class RuntimeContext:
    agent_id: str
    thread_id: str
    event_id: str | None
    agent_settings: dict[str, Any]
    organization_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    user_name: str = ""
    channel: str = ""
    knowledge_bases: list[str] = field(default_factory=list)
    thread_documents: list[ProcessedDocument] = field(default_factory=list)
    skills: list[SkillSpec] = field(default_factory=list)
    loaded_skills: set[str] = field(default_factory=set)
    tools_called: list[str] = field(default_factory=list)

    def load_skill(self, skill_id: str) -> None:
        self.loaded_skills.add(skill_id)

    def record_tool_call(self, name: str) -> None:
        self.tools_called.append(name)

    def state_message(self) -> str:
        lines = ["# RUNTIME CONTEXT", f"Current date: {date.today().isoformat()}"]
        if self.channel:
            lines.append(f"Channel: {self.channel}")
        if self.user_name:
            lines.append(f"User name: {self.user_name}")
        if self.knowledge_bases:
            lines.append("Private knowledge bases with content: " + ", ".join(self.knowledge_bases))
        else:
            lines.append("No private knowledge base has content; do not call search_knowledge.")
        manifest = build_document_manifest(self.thread_documents)
        lines.append("")
        lines.append(manifest or "No documents are attached to this thread.")
        if self.loaded_skills:
            lines.append("Skills already loaded earlier in this conversation (do not load again): " + ", ".join(sorted(self.loaded_skills)))
        return "\n".join(lines)

    @classmethod
    def from_history(
        cls,
        *,
        agent_id: str,
        thread_id: str,
        event_id: str | None,
        agent_settings: dict[str, Any],
        history_items: list[dict[str, Any]],
        **extra: Any,
    ) -> RuntimeContext:
        runtime = cls(
            agent_id=agent_id,
            thread_id=thread_id,
            event_id=event_id,
            agent_settings=agent_settings,
            skills=compile_skills(agent_settings),
            **extra,
        )
        for item in history_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "function_call_output" or item.get("role") == "tool":
                for skill_id in loaded_skill_ids_from_text(_output_text(item.get("output") or item.get("content"))):
                    runtime.load_skill(skill_id)
        return runtime


def _output_text(value: Any) -> str:
    if isinstance(value, dict):
        nested = value.get("output")
        return str(nested if nested is not None else json.dumps(value, ensure_ascii=False, default=str))
    if isinstance(value, list):
        return " ".join(_output_text(v) for v in value)
    if not isinstance(value, str):
        return str(value or "")
    text = value.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, dict) and parsed.get("output") is not None:
        return str(parsed["output"])
    return text
