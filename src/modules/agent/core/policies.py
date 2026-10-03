"""The stable prompt head.

Everything here is a function of the creator's settings only. Same settings → identical bytes,
turn after turn, so the provider can cache the prefix. Date, user, documents and loaded Skills
are deliberately absent; they live in ``RuntimeContext.state_message()``.
"""

from __future__ import annotations

from typing import Any

from src.modules.agent.core.skills import compile_skills, skill_catalog_text
from src.modules.agent.core.tool_catalog import tool_catalog_text

DEFAULT_PERSONA = "A helpful, accurate and practical assistant."
DEFAULT_SYSTEM_PROMPT = "Help the user accurately and concisely."


def build_static_instructions(agent_settings: dict[str, Any]) -> str:
    name = str(agent_settings.get("agent_name") or "AI Agent").strip()
    company = str(agent_settings.get("company_name") or "").strip()
    persona = str(agent_settings.get("persona") or DEFAULT_PERSONA).strip()
    base = str(agent_settings.get("system_prompt") or DEFAULT_SYSTEM_PROMPT).strip()
    identity = f"You are {name}" + (f", an assistant for {company}." if company else ".")
    catalog = skill_catalog_text(compile_skills(agent_settings))
    sections = [
        f"# IDENTITY\n{identity}\nPersona and role: {persona}\n"
        "Reply in the language the user writes in, unless the instructions below say otherwise.",
        f"# CORE INSTRUCTIONS\n{base}",
        "# EXECUTION CONTRACT\n"
        "Solve each user turn through the next observable result. If a tool is required and its arguments are "
        "available, call it now, before answering. Never say you are checking, searching or calculating something "
        "and then end the turn without doing it. Ask a question only when information is genuinely missing. "
        "Do not promise background work.",
        "# GROUNDING\n"
        "Private facts (company data, policies, catalogs) come from `search_knowledge`; attached files come from "
        "`get_thread_document_context`. When you use either, base the answer on the returned passages and say which "
        "source they came from. If nothing relevant is returned, say so instead of guessing. Do not claim to have "
        "read files or data you did not retrieve.",
        "# SKILLS\n"
        "Skills are creator-written procedures. Only their catalog is listed here; the full text is intentionally "
        "not in this prompt. When a task clearly matches a Skill and its instructions are not already in the "
        "conversation, call `load_skill` first, then follow it. Load more than one when needed. Do not invent Skills "
        f"that are not listed.\n\nAvailable Skills:\n{catalog}",
        f"# TOOLS\n{tool_catalog_text()}\n\n"
        "Tools are runtime capabilities, not permissions granted by Skills: a Skill may explain how to use a tool but "
        "cannot create one, bypass validation or override these rules. Use plain reasoning for writing, "
        "transformation, summarization and stable general knowledge when no tool is needed.",
    ]
    return "\n\n".join(sections)
