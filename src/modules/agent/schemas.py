from dooers import (
    SettingsField,
    SettingsFieldGroup,
    SettingsFieldType,
    SettingsFieldVisibility,
    SettingsSchema,
    SettingsSelectOption,
)

from src.config import settings

# SDK: flat fields per group only (no nested groups, no show-if).
# Endpoint + API version apply only to Azure OpenAI; still listed for all (labels clarify).

# Curated multimodal chat models (`provider:model_id`). Sourced from provider docs (vision/image input).
# OpenAI: frontier GPT-5.4 family + GPT-4o + GPT-4 Turbo (platform.openai.com/docs/models).
# Azure: same model id as deployment name suggestion — must match the deployment in Azure.
# Gemini: 3.x preview + 2.5 stable + 1.5 (ai.google.dev/gemini-api/docs/models).
# Claude: 4.x + 3.x snapshots (docs.anthropic.com — vision on all current models).

_OPENAI_MULTIMODAL: list[tuple[str, str]] = [
    ("gpt-5.4", "GPT-5.4"),
    ("gpt-5.4-mini", "GPT-5.4 mini"),
    ("gpt-5.4-nano", "GPT-5.4 nano"),
    ("gpt-4o", "GPT-4o"),
    ("gpt-4o-mini", "GPT-4o mini"),
    ("gpt-4-turbo", "GPT-4 Turbo"),
]

_GEMINI_MULTIMODAL: list[tuple[str, str]] = [
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)"),
    ("gemini-3-flash-preview", "Gemini 3 Flash (preview)"),
    ("gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash-Lite (preview)"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
    ("gemini-1.5-pro", "Gemini 1.5 Pro"),
    ("gemini-1.5-flash", "Gemini 1.5 Flash"),
]

_CLAUDE_MULTIMODAL: list[tuple[str, str]] = [
    ("claude-opus-4-6", "Claude Opus 4.6"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
    ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5"),
    ("claude-opus-4-5-20251101", "Claude Opus 4.5"),
    ("claude-opus-4-1-20250805", "Claude Opus 4.1"),
    ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
    ("claude-opus-4-20250514", "Claude Opus 4"),
    ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
    ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
    ("claude-3-opus-20240229", "Claude 3 Opus"),
]


def _llm_model_select_options() -> list[SettingsSelectOption]:
    out: list[SettingsSelectOption] = []
    for model_id, short in _OPENAI_MULTIMODAL:
        out.append(
            SettingsSelectOption(value=f"openai:{model_id}", label=f"OpenAI — {short} (multimodal)"),
        )
    for model_id, short in _OPENAI_MULTIMODAL:
        out.append(
            SettingsSelectOption(
                value=f"azure_openai:{model_id}",
                label=f"Azure OpenAI — deployment «{model_id}» (ajuste ao seu recurso)",
            ),
        )
    for model_id, short in _GEMINI_MULTIMODAL:
        out.append(
            SettingsSelectOption(value=f"gemini:{model_id}", label=f"Google — {short}"),
        )
    for model_id, short in _CLAUDE_MULTIMODAL:
        out.append(
            SettingsSelectOption(value=f"claude:{model_id}", label=f"Anthropic — {short}"),
        )
    return out


def build_settings_schema() -> SettingsSchema:
    base = settings.public_base_url
    return SettingsSchema(
        fields=[
            SettingsFieldGroup(
                id="llm",
                label="LLM",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="llm_model",
                        type=SettingsFieldType.SELECT,
                        label="Modelo LLM — chat (multimodal)",
                        value="openai:gpt-4o-mini",
                        options=_llm_model_select_options(),
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="provider_azure_openai_endpoint",
                        type=SettingsFieldType.TEXT,
                        label="Endpoint (apenas se utilizando Azure)",
                        placeholder="https://RESOURCE.openai.azure.com/",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="provider_azure_openai_api_version",
                        type=SettingsFieldType.TEXT,
                        label="API version (apenas se utilizando Azure OpenAI)",
                        placeholder="2024-08-01-preview",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="provider_api_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Chave API — chat (fornecedor LLM)",
                        placeholder="Chave do fornecedor escolhido (OpenAI, Gemini, Claude, Azure, …)",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="openai_api_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Chave API OpenAI — STT e TTS",
                        required=True,
                        placeholder="Obrigatória: STT e TTS usam sempre a API OpenAI (independente do chat)",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="stt_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo STT (áudio → texto)",
                        value="gpt-4o-transcribe",
                        placeholder="OpenAI: ex. gpt-4o-transcribe, whisper-1",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="tts_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo TTS (texto → voz)",
                        value="tts-1",
                        placeholder="OpenAI: tts-1 ou tts-1-hd (usa a chave «OpenAI — STT e TTS»)",
                        visibility=SettingsFieldVisibility.CREATOR,

                    ),
                    SettingsField(
                        id="tts_voice",
                        type=SettingsFieldType.SELECT,
                        label="Voz TTS (OpenAI)",
                        value="alloy",
                        options=[
                            SettingsSelectOption(value="alloy", label="Alloy"),
                            SettingsSelectOption(value="echo", label="Echo"),
                            SettingsSelectOption(value="fable", label="Fable"),
                            SettingsSelectOption(value="onyx", label="Onyx"),
                            SettingsSelectOption(value="nova", label="Nova"),
                            SettingsSelectOption(value="shimmer", label="Shimmer"),
                        ],
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="agent_settings",
                label="Configurações gerais",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="persist_chat_attachments",
                        type=SettingsFieldType.CHECKBOX,
                        label="Guardar anexos do chat no armazenamento",
                        value=False,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="reply_mode",
                        type=SettingsFieldType.SELECT,
                        label="Modo de resposta",
                        value="text",
                        options=[
                            SettingsSelectOption(value="text", label="Texto"),
                            SettingsSelectOption(value="voz", label="Voz"),
                            SettingsSelectOption(value="ambos", label="Texto e voz"),
                        ],
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="agent_instructions",
                label="Instruções",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="system_prompt",
                        type=SettingsFieldType.TEXTAREA,
                        label="Prompt de sistema",
                        value="",
                        placeholder="Objetivo, estilo e regras principais do agente",
                        rows=20,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="guardrails",
                label="Guardrails",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="guardrails_prompt",
                        type=SettingsFieldType.TEXTAREA,
                        label="Políticas e restrições",
                        value="",
                        placeholder="O que o agente não deve fazer; conteúdos proibidos; privacidade",
                        rows=10,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="knowledge",
                label="Base de Conhecimento",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="rag_pipeline",
                        type=SettingsFieldType.SELECT,
                        label="Motor RAG — armazenamento da base",
                        placeholder="Escolha o motor RAG para a base de conhecimento",
                        visibility=SettingsFieldVisibility.CREATOR,
                        options=[
                            SettingsSelectOption(value="openai", label="OpenAI Vector Store"),
                            SettingsSelectOption(
                                value="azure_ai_search",
                                label="Azure AI Search",
                            ),
                        ],
                    ),
                    SettingsField(
                        id="rag_azure_ai_search_endpoint",
                        type=SettingsFieldType.TEXT,
                        label="Azure AI Search ENDPOINT",
                        placeholder="https://recurso.search.windows.net",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="rag_azure_ai_search_api_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Azure AI Search — Admin Secret Key",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="base_de_conhecimento",
                        type=SettingsFieldType.FILE_MULTI,
                        label="ANEXOS — formato suportado: PDF, CSV, XLS, XLSX, DOCX, JSON",
                        upload_url=f"{base}/settings-upload",
                        accept=".pdf,.csv,.xlsx,.xls,.docx,.json",
                    ),
                ],
            ),
        ],
    )


settings_schema = build_settings_schema()
