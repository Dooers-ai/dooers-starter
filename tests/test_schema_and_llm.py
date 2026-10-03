from src.modules.agent.schemas import settings_schema
from src.modules.helpers.llm_provider import build_agents_run_config, resolve_agents_wire_format
from src.modules.llm.factory import resolve_chat_model
from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_ID

REQUIRED_FIELD_IDS = {
    "llm_models",
    "reasoning_effort",
    "agent_name",
    "persona",
    "system_prompt",
    "skills",
    "guardrails_prompt",
    KNOWLEDGE_FIELD_ID,
    "reply_mode",
}


def test_schema_exposes_fields_code_depends_on():
    for field_id in REQUIRED_FIELD_IDS:
        assert settings_schema.get_field(field_id) is not None, field_id
    assert settings_schema.get_field("skills").upload_url.endswith("/skills-upload")
    assert settings_schema.get_field(KNOWLEDGE_FIELD_ID).upload_url.endswith("/settings-upload")


def test_gateway_uses_chat_completions_wire():
    assert resolve_agents_wire_format() == "openai_completions"


def test_model_resolution_strips_legacy_prefix_and_respects_allowlist():
    assert resolve_chat_model({"llm_model": "openai:gpt-5.6-sol"}) == "gpt-5.6-sol"
    assert resolve_chat_model({"llm_models": "glm-5-maas"}, allowed=("glm-5-maas",)) == "glm-5-maas"
    assert resolve_chat_model({}, allowed=("gemini-3.8-flash",)) == "gemini-3.8-flash"


def test_run_config_sets_prompt_cache_key():
    cfg = build_agents_run_config({"reasoning_effort": "low"}, model="gemini-3.8-flash", prompt_cache_key="k")
    assert cfg.model == "gemini-3.8-flash"
    assert cfg.model_settings.extra_args["prompt_cache_key"] == "k"
