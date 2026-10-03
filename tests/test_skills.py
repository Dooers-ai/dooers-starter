import pytest

from src.modules.agent.core.skills import (
    SKILL_LOADED_MARKER,
    builtin_skills,
    compile_skills,
    find_skill,
    load_skill_reply,
    loaded_skill_ids_from_text,
    parse_skill_markdown,
)

VALID = """---
id: refund-policy
name: Refund policy
description: Handle refund requests.
requires_tools: [search_knowledge, calculate]
---
1. Search the knowledge base.
"""


def test_parse_valid_skill():
    spec = parse_skill_markdown(VALID, filename="refund.md")
    assert spec.id == "refund-policy"
    assert spec.required_tools == ("search_knowledge", "calculate")
    assert spec.instructions.startswith("1. Search")


@pytest.mark.parametrize(
    "bad",
    [
        "no frontmatter",
        "---\nid: x\n---\nbody",  # missing name/description, id too short
        "---\nid: ok-id\nname: N\ndescription: D\nrequires_tools: [nope_tool]\n---\nbody",
        "---\nid: ok-id\nname: N\ndescription: D\nunknown: 1\n---\nbody",
        "---\nid: ok-id\nname: N\ndescription: D\n---\n",
    ],
)
def test_parse_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_skill_markdown(bad)


def test_builtin_skills_are_valid_and_studio_overrides():
    builtin = builtin_skills()
    assert any(s.id == "document-review" for s in builtin)
    override = VALID.replace("refund-policy", "document-review")
    merged = compile_skills({"skills": [{"filename": "x.md", "content": override}]})
    doc = find_skill(merged, "document-review")
    assert doc is not None and doc.source == "studio"


def test_load_reply_marker_roundtrip():
    spec = parse_skill_markdown(VALID)
    reply = load_skill_reply(spec)
    assert reply.startswith(SKILL_LOADED_MARKER.format(skill_id="refund-policy"))
    assert loaded_skill_ids_from_text(reply) == ["refund-policy"]
