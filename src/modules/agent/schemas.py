from dooers.agents.server import (
    SettingsField,
    SettingsFieldGroup,
    SettingsFieldType,
    SettingsFieldVisibility,
    SettingsSchema,
    SettingsSelectOption,
)

from src.config import settings

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
        out.append(SettingsSelectOption(value=f"openai:{model_id}", label=f"OpenAI — {short}"))
    for model_id, short in _OPENAI_MULTIMODAL:
        out.append(
            SettingsSelectOption(
                value=f"azure_openai:{model_id}",
                label=f"Azure OpenAI — deployment «{model_id}»",
            )
        )
    for model_id, short in _GEMINI_MULTIMODAL:
        out.append(SettingsSelectOption(value=f"gemini:{model_id}", label=f"Google — {short}"))
    for model_id, short in _CLAUDE_MULTIMODAL:
        out.append(SettingsSelectOption(value=f"claude:{model_id}", label=f"Anthropic — {short}"))
    return out


def build_settings_schema() -> SettingsSchema:
    return SettingsSchema(
        fields=[
            # ── 1. Identidade do agente ───────────────────────────────────────
            SettingsFieldGroup(
                id="identidade",
                label="Identidade do agente",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="agent_name",
                        type=SettingsFieldType.TEXT,
                        label="Nome do agente",
                        value="Assistente",
                        placeholder="Ex: Bella, Sofia, Atendente Rede…",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="reply_mode",
                        type=SettingsFieldType.SELECT,
                        label="Modo de resposta",
                        value="text",
                        options=[
                            SettingsSelectOption(value="text", label="Somente texto"),
                            SettingsSelectOption(value="voz", label="Somente voz"),
                            SettingsSelectOption(value="ambos", label="Texto e voz"),
                        ],
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            # ── 2. Instruções ─────────────────────────────────────────────────
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
            # ── 3. WhatsApp ───────────────────────────────────────────────────
            SettingsFieldGroup(
                id="whatsapp",
                label="WhatsApp",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="gestor_phone",
                        type=SettingsFieldType.TEXT,
                        label="Telefone do gestor (E.164)",
                        placeholder="+5511999999999 — para notificações internas",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="whatsapp_grupo_geral",
                        type=SettingsFieldType.TEXT,
                        label="ID do grupo geral de franqueados",
                        placeholder="120363XXXXXXXXXX@g.us — usado no anúncio de treinamentos",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            # ── 4. Recrutamento ───────────────────────────────────────────────
            SettingsFieldGroup(
                id="recrutamento",
                label="Recrutamento",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="link_avaliacao_comportamental",
                        type=SettingsFieldType.TEXT,
                        label="Link da avaliação comportamental (Tally)",
                        placeholder="https://tally.so/r/XXXXXX — enviado ao candidato no primeiro contato",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            # ── 5. Banco de dados ─────────────────────────────────────────────
            SettingsFieldGroup(
                id="database",
                label="Banco de dados (Supabase)",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="supabase_url",
                        type=SettingsFieldType.TEXT,
                        label="URL do projeto Supabase",
                        placeholder="https://XXXXXXXXXXXX.supabase.co",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="supabase_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Chave de serviço Supabase (service_role)",
                        placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tally_signing_secret",
                        type=SettingsFieldType.PASSWORD,
                        label="Segredo HMAC dos webhooks Tally",
                        placeholder="Deixe vazio para desabilitar a verificação de assinatura (dev)",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            # ── 6. LLM ────────────────────────────────────────────────────────
            SettingsFieldGroup(
                id="llm",
                label="LLM",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="llm_model",
                        type=SettingsFieldType.SELECT,
                        label="Modelo de chat (multimodal)",
                        value="openai:gpt-4o-mini",
                        options=_llm_model_select_options(),
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="provider_azure_openai_endpoint",
                        type=SettingsFieldType.TEXT,
                        label="Endpoint Azure OpenAI (somente Azure)",
                        placeholder="https://RESOURCE.openai.azure.com/",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="provider_azure_openai_api_version",
                        type=SettingsFieldType.TEXT,
                        label="API version Azure OpenAI (somente Azure)",
                        placeholder="2024-08-01-preview",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="provider_api_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Chave API do fornecedor de chat",
                        placeholder="OpenAI, Gemini, Anthropic ou Azure — conforme modelo escolhido",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="openai_api_key",
                        type=SettingsFieldType.PASSWORD,
                        label="Chave API OpenAI — STT / TTS / análise de currículos",
                        required=True,
                        placeholder="Obrigatória: transcrição de áudio, voz e análise de PDF usam GPT-4o",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="stt_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo STT (áudio → texto)",
                        value="gpt-4o-transcribe",
                        placeholder="Ex: gpt-4o-transcribe, whisper-1",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tts_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo TTS (texto → voz)",
                        value="tts-1",
                        placeholder="OpenAI: tts-1 ou tts-1-hd",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tts_voice",
                        type=SettingsFieldType.SELECT,
                        label="Voz TTS",
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
            # ── 7. Guardrails ─────────────────────────────────────────────────
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
            # ── 8. Avançado ───────────────────────────────────────────────────
            SettingsFieldGroup(
                id="advanced",
                label="Avançado",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="persist_chat_attachments",
                        type=SettingsFieldType.CHECKBOX,
                        label="Guardar anexos do chat no armazenamento",
                        value=False,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
        ],
    )


settings_schema = build_settings_schema()
