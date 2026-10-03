from src.modules.agent.core.context import RuntimeContext
from src.modules.agent.core.policies import build_static_instructions
from src.modules.agent.core.tool_catalog import TOOL_NAMES
from src.modules.agent.core.tools import ALL_TOOLS
from src.modules.agent.workflow import prompt_cache_key

SETTINGS = {"agent_name": "Bot", "system_prompt": "Be brief.", "skills": []}


def test_static_prompt_is_stable_and_lists_skills_and_tools():
    a = build_static_instructions(SETTINGS)
    b = build_static_instructions(dict(SETTINGS))
    assert a == b
    assert "document-review" in a
    for name in TOOL_NAMES:
        assert f"`{name}`" in a
    assert not a.startswith(" ")


def test_tool_catalog_matches_registered_tools():
    assert {t.name for t in ALL_TOOLS} == set(TOOL_NAMES)


def test_runtime_context_rehydrates_loaded_skills_from_tool_trail():
    history = [
        {"role": "user", "content": "oi"},
        {"role": "tool", "content": "Skill 'document-review' loaded.\nName: x"},
    ]
    runtime = RuntimeContext.from_history(agent_id="a", thread_id="t", event_id="e", agent_settings=SETTINGS, history_items=history)
    assert runtime.loaded_skills == {"document-review"}
    state = runtime.state_message()
    assert "document-review" in state
    assert "No documents are attached" in state
    assert "do not call search_knowledge" in state


def test_prompt_cache_key_is_sharded_per_agent():
    k1 = prompt_cache_key("agent", "thread-1")
    k2 = prompt_cache_key("agent", "thread-1")
    assert k1 == k2 and k1.startswith("starter:v1:agent:shard-")
