"""Studio settings schema — what the creator (and, where allowed, the end user) can configure.

Groups: model (synced from the Dooers Gateway allow-list), identity, skills, guardrails,
knowledge, audio, general. Field ids are referenced by code; rename with care.
"""

from __future__ import annotations

from dooers.agents.server import (
    SettingsField,
    SettingsFieldGroup,
    SettingsFieldType,
    SettingsFieldVisibility,
    SettingsSchema,
    SettingsSelectOption,
)

from src.config import settings
from src.modules.agent.core.tool_catalog import tool_catalog_text
from src.modules.llm.gateway_models import LLM_MODELS_FIELD_ID, cached_model_options
from src.modules.rag.ingest_filename import RAG_INGEST_ACCEPT
from src.modules.rag.knowledge_settings import KNOWLEDGE_FIELD_ID


def _model_options() -> list[SettingsSelectOption]:
    # Placeholder until the lifespan syncs the real allow-list from the gateway (/v1/models).
    return [SettingsSelectOption(value=value, label=label) for value, label in cached_model_options()]


def build_settings_schema() -> SettingsSchema:
    base = settings.public_base_url
    return SettingsSchema(
        fields=[
            SettingsFieldGroup(
                id="llm",
                label="Modelo",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id=LLM_MODELS_FIELD_ID,
                        type=SettingsFieldType.SELECT,
                        label="Modelo LLM (Dooers Gateway)",
                        value=settings.default_llm_model,
                        options=_model_options(),
                        visibility=SettingsFieldVisibility.USER,
                        user_editable=False,
                    ),
                    SettingsField(
                        id="reasoning_effort",
                        type=SettingsFieldType.SELECT,
                        label="Esforço de raciocínio",
                        value="medium",
                        options=[
                            SettingsSelectOption(value="low", label="Baixo (mais rápido)"),
                            SettingsSelectOption(value="medium", label="Médio"),
                            SettingsSelectOption(value="high", label="Alto (tarefas complexas)"),
                        ],
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="identity",
                label="Identidade e instruções",
                collapsible="open",
                fields=[
                    SettingsField(
                        id="agent_name",
                        type=SettingsFieldType.TEXT,
                        label="Nome do agente",
                        value=settings.assistant_name,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="company_name",
                        type=SettingsFieldType.TEXT,
                        label="Empresa / contexto",
                        value="",
                        placeholder="Para quem este agente trabalha",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="persona",
                        type=SettingsFieldType.TEXTAREA,
                        label="Persona",
                        value="",
                        placeholder="Papel, tom de voz, público. Ex.: consultor técnico, direto e cordial.",
                        rows=4,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="system_prompt",
                        type=SettingsFieldType.TEXTAREA,
                        label="Instruções principais",
                        value="",
                        placeholder="Objetivo do agente, regras de negócio estáveis, formato das respostas",
                        rows=16,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="skills",
                label="Skills (capacidades progressivas)",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="skills",
                        type=SettingsFieldType.FILE_MULTI,
                        label="Skills em Markdown (frontmatter: id, name, description, requires_tools)",
                        upload_url=f"{base}/skills-upload",
                        accept=".md,.markdown",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tool_catalog",
                        type=SettingsFieldType.TEXTAREA,
                        label="Ferramentas disponíveis (referência para Skills)",
                        value=tool_catalog_text(),
                        rows=6,
                        readonly=True,
                        visibility=SettingsFieldVisibility.CREATOR,
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
                        label="Políticas (entrada e saída)",
                        value="",
                        placeholder="O que o agente não deve aceitar nem responder; privacidade; temas proibidos",
                        rows=8,
                    ),
                    SettingsField(
                        id="input_guardrails_prompt",
                        type=SettingsFieldType.TEXTAREA,
                        label="Políticas só para mensagens recebidas (opcional)",
                        value="",
                        rows=4,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="output_guardrails_prompt",
                        type=SettingsFieldType.TEXTAREA,
                        label="Políticas só para respostas (opcional)",
                        value="",
                        rows=4,
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="knowledge",
                label="Base de conhecimento (RAG Dooers)",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id=KNOWLEDGE_FIELD_ID,
                        type=SettingsFieldType.FILE_MULTI,
                        label="Documentos — PDF, CSV, XLS, XLSX, DOCX, JSON, TXT, MD",
                        upload_url=f"{base}/settings-upload",
                        accept=RAG_INGEST_ACCEPT,
                    ),
                ],
            ),
            SettingsFieldGroup(
                id="audio",
                label="Áudio (STT/TTS via OpenAI)",
                collapsible="closed",
                fields=[
                    SettingsField(
                        id="stt_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo STT",
                        value="gpt-4o-mini-transcribe",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tts_model",
                        type=SettingsFieldType.TEXT,
                        label="Modelo TTS",
                        value="gpt-4o-mini-tts",
                        visibility=SettingsFieldVisibility.CREATOR,
                    ),
                    SettingsField(
                        id="tts_voice",
                        type=SettingsFieldType.SELECT,
                        label="Voz TTS",
                        value="alloy",
                        options=[
                            SettingsSelectOption(value=v, label=v.capitalize())
                            for v in ("alloy", "echo", "fable", "onyx", "nova", "shimmer")
                        ],
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
                id="general",
                label="Geral",
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
