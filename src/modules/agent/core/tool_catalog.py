"""The stable tool surface.

Tool names are a contract: Skills reference them, Studio shows them, tests pin them. Adding a
domain tool means adding a ``ToolSpec`` here, the implementation in ``tools.py`` and the entry
in ``agent.build_agent``. Keeping the list static keeps the prompt prefix byte-stable across
turns, which is what makes provider prompt caching effective.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("load_skill", "Loads the full instructions of a configured Skill on demand."),
    ToolSpec("search_knowledge", "Searches the agent's private knowledge bases (managed Dooers RAG)."),
    ToolSpec("get_thread_document_context", "Reads or searches documents attached to the current conversation."),
    ToolSpec("calculate", "Evaluates arithmetic deterministically."),
)

TOOL_NAMES: frozenset[str] = frozenset(spec.name for spec in TOOL_SPECS)


def tool_catalog_text() -> str:
    return "\n".join(f"- `{spec.name}` — {spec.description}" for spec in TOOL_SPECS)
