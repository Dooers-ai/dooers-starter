"""Skills: Markdown procedures the agent loads only when a task needs them.

A Skill is a file with a small YAML frontmatter and a Markdown body::

    ---
    id: refund-policy
    name: Refund policy
    description: How to handle refund and exchange requests.
    requires_tools: [search_knowledge]
    ---
    1. Search the knowledge base for the current refund terms ...

Two sources are merged: files in the repository ``skills/`` folder (shipped with the code) and
files the creator uploads in Studio (``skills`` FILE_MULTI field). The prompt only carries the
catalog (id + description); the body enters the conversation through the ``load_skill`` tool
result, so a dozen Skills cost a few hundred tokens until one is actually used.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import settings
from src.modules.agent.core.tool_catalog import TOOL_NAMES

logger = logging.getLogger(__name__)

SKILLS_FIELD_ID = "skills"
SKILL_LOADED_MARKER = "Skill '{skill_id}' loaded."
_SKILL_MARKER_RE = re.compile(r"Skill '([^']+)' loaded\.")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
_FRONTMATTER_KEYS = {"id", "name", "description", "requires_tools"}


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    description: str
    instructions: str
    required_tools: tuple[str, ...]
    filename: str
    source: str = "studio"  # "builtin" | "studio"


def _parse_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    text = (markdown or "").replace("\r\n", "\n").strip()
    if not text.startswith("---\n"):
        raise ValueError("Skill must start with YAML frontmatter delimited by '---'.")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Skill frontmatter must end with a second '---' line.")
    header, body = text[4:end], text[end + 5 :].strip()
    if not body:
        raise ValueError("Skill instructions body cannot be empty.")

    data: dict[str, Any] = {}
    active_list: str | None = None
    for raw in header.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            if active_list is None:
                raise ValueError("List item found without a list field in Skill frontmatter.")
            value = stripped[1:].strip().strip("\"'")
            if not value:
                raise ValueError(f"Empty value in {active_list}.")
            data.setdefault(active_list, []).append(value)
            continue
        if ":" not in line:
            raise ValueError(f"Invalid Skill frontmatter line: {stripped}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key not in _FRONTMATTER_KEYS:
            raise ValueError(f"Unknown Skill frontmatter field: {key}")
        if key == "requires_tools":
            active_list = key
            data[key] = []
            if value:
                if value.startswith("[") and value.endswith("]"):
                    data[key] = [p.strip().strip("\"'") for p in value[1:-1].split(",") if p.strip()]
                else:
                    raise ValueError("requires_tools must be a YAML list or [tool_a, tool_b].")
        else:
            active_list = None
            if not value:
                raise ValueError(f"Skill frontmatter field '{key}' cannot be empty.")
            data[key] = value
    return data, body


def parse_skill_markdown(markdown: str, *, filename: str = "skill.md", source: str = "studio") -> SkillSpec:
    meta, body = _parse_frontmatter(markdown)
    missing = sorted({"id", "name", "description"} - set(meta))
    if missing:
        raise ValueError("Missing Skill frontmatter fields: " + ", ".join(missing))
    skill_id = str(meta["id"]).strip().lower()
    if not _ID_RE.fullmatch(skill_id):
        raise ValueError("Skill id must match [a-z0-9][a-z0-9_-]{1,79}.")
    name, description = str(meta["name"]).strip(), str(meta["description"]).strip()
    if len(name) > 120:
        raise ValueError("Skill name must be at most 120 characters.")
    if len(description) > 500:
        raise ValueError("Skill description must be at most 500 characters.")
    tools_raw = meta.get("requires_tools", [])
    if not isinstance(tools_raw, list):
        raise ValueError("requires_tools must be a list.")
    required = tuple(dict.fromkeys(str(t).strip() for t in tools_raw if str(t).strip()))
    unknown = sorted(set(required) - TOOL_NAMES)
    if unknown:
        raise ValueError("Skill references unknown tools: " + ", ".join(unknown))
    return SkillSpec(skill_id, name, description, body, required, filename, source)


def parse_skill_upload(item: dict[str, Any]) -> SkillSpec | None:
    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    filename = str(item.get("filename") or "skill.md").strip() or "skill.md"
    return parse_skill_markdown(content, filename=filename, source="studio")


@lru_cache(maxsize=1)
def builtin_skills() -> tuple[SkillSpec, ...]:
    """Skills shipped in the repository ``skills/`` folder (read once per process)."""
    folder = Path(settings.skills_dir)
    if not folder.is_absolute():
        folder = Path(__file__).resolve().parents[4] / folder
    if not folder.is_dir():
        return ()
    out: list[SkillSpec] = []
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            out.append(parse_skill_markdown(path.read_text(encoding="utf-8"), filename=path.name, source="builtin"))
        except ValueError as exc:
            logger.warning("Ignoring invalid built-in Skill %s: %s", path.name, exc)
    return tuple(out)


def compile_skills(agent_settings: dict[str, Any]) -> list[SkillSpec]:
    """Built-in Skills plus Studio uploads; a Studio Skill with the same id overrides the built-in."""
    merged: dict[str, SkillSpec] = {skill.id: skill for skill in builtin_skills()}
    raw = agent_settings.get(SKILLS_FIELD_ID)
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            spec = parse_skill_upload(item)
        except ValueError as exc:
            logger.warning("Ignoring invalid uploaded Skill %s: %s", item.get("filename"), exc)
            continue
        if spec is not None:
            merged[spec.id] = spec
    return list(merged.values())


def skill_catalog_text(skills: list[SkillSpec]) -> str:
    if not skills:
        return "No Skills are configured for this agent."
    lines = []
    for skill in skills:
        tools = ", ".join(f"`{t}`" for t in skill.required_tools) or "none"
        lines.append(f"- `{skill.id}` — {skill.name}: {skill.description} Tools: {tools}.")
    return "\n".join(lines)


def find_skill(skills: list[SkillSpec], value: str) -> SkillSpec | None:
    needle = (value or "").strip().casefold()
    if not needle:
        return None
    for skill in skills:
        if needle in {skill.id.casefold(), skill.name.casefold(), skill.filename.casefold()}:
            return skill
    return None


def load_skill_reply(skill: SkillSpec) -> str:
    tools = ", ".join(skill.required_tools) or "none"
    return (
        f"{SKILL_LOADED_MARKER.format(skill_id=skill.id)}\n"
        f"Name: {skill.name}\n"
        f"Tools this Skill relies on: {tools}\n\n"
        f"# SKILL INSTRUCTIONS\n{skill.instructions}"
    )


def loaded_skill_ids_from_text(text: str) -> list[str]:
    return [m.strip() for m in _SKILL_MARKER_RE.findall(text or "") if m.strip()]
