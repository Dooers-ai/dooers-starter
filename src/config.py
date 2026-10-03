"""Process-level configuration.

Two kinds of settings live here:

* **Bootstrap** values injected by Dooers Hosting or your local ``.env`` (port, database,
  gateway key, RAG service URL, storage). They are process-wide and never editable from Studio.
* **Defaults** for things the creator may later override per agent in Studio (model, prompt,
  Skills, knowledge). Those live in ``agent_settings`` at request time — see ``schemas.py``.

Everything the agent needs from the platform comes through four env vars that ``dooers run`` /
``dooers push`` provide: ``DOOERS_GATEWAY_API_KEY`` (LLM), ``DOOERS_RAG_SERVICE_URL`` (knowledge),
``AGENT_DATABASE_*`` (threads/settings) and ``AGENT_SEED_SECRET`` (service identity).
"""

from __future__ import annotations

import os
import sys

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GATEWAY_BASE_URL = "https://llm.dooers.ai/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # --- HTTP -----------------------------------------------------------------
    http_port: int = Field(default=8000, validation_alias=AliasChoices("HTTP_PORT", "PORT"))
    #: Mount routes under ``/api/{env}/{name}``. Keep False for Dooers Hosting (the load balancer
    #: strips ``/<agent-id>`` and the agent must serve at ``/``, matching ``message_path: /``).
    use_prefix: bool = Field(default=False, validation_alias=AliasChoices("USE_API_PREFIX"))
    api_environment: str = "dev"
    api_agent_name: str = Field(default="dooers-starter", validation_alias=AliasChoices("API_AGENT_NAME"))
    logging_level: str = Field(default="INFO", validation_alias=AliasChoices("LOGGING_LEVEL"))
    #: True → configuration problems abort boot (local/CI). False → log and boot degraded so the
    #: hosted readiness check passes and the problem is visible in the thread instead of a crash loop.
    config_strict: bool = Field(default=False, validation_alias=AliasChoices("CONFIG_STRICT"))
    service_url: str = Field(default="http://localhost:8000", validation_alias=AliasChoices("SERVICE_URL"))
    assistant_name: str = Field(default="Assistant", validation_alias=AliasChoices("ASSISTANT_NAME"))

    # --- Persistence (SDK) ------------------------------------------------------
    #: "postgres" (your DB via AGENT_DATABASE_*) or "dooers" (managed AlloyDB, injected on push).
    agent_database_type: str = Field(default="postgres", validation_alias=AliasChoices("AGENT_DATABASE_TYPE"))
    agent_database_host: str = Field(default="localhost", validation_alias=AliasChoices("AGENT_DATABASE_HOST"))
    agent_database_port: int = Field(default=5432, validation_alias=AliasChoices("AGENT_DATABASE_PORT"))
    agent_database_user: str = Field(default="postgres", validation_alias=AliasChoices("AGENT_DATABASE_USER"))
    agent_database_name: str = Field(default="dooers_agent", validation_alias=AliasChoices("AGENT_DATABASE_NAME"))
    agent_database_password: str = Field(default="", validation_alias=AliasChoices("AGENT_DATABASE_PASSWORD"))
    agent_database_ssl: bool | str = Field(default=False, validation_alias=AliasChoices("AGENT_DATABASE_SSL"))

    # --- LLM: Dooers Gateway first ---------------------------------------------
    #: ``dk_live_…`` key. The gateway exposes only the models allow-listed for this key.
    dooers_gateway_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DOOERS_GATEWAY_API_KEY", "DOOERS_GATEWAY_KEY", "DOOERS_API_KEY", "DOOERS_LLM_TOKEN"),
    )
    dooers_gateway_base_url: str = Field(
        default=DEFAULT_GATEWAY_BASE_URL,
        validation_alias=AliasChoices("DOOERS_GATEWAY_BASE_URL", "DOOERS_GATEWAY_URL", "DOOERS_LLM_BASE_URL"),
    )
    #: Preferred chat model when the key allows it; otherwise the first allow-listed model.
    # GLM-5 is the verified default for tool calling through the gateway's Chat Completions dialect.
    # Gemini 3.x returns UPSTREAM_ERROR there when tools are present (as of 2026-10); switch once fixed.
    default_llm_model: str = Field(default="glm-5-maas", validation_alias=AliasChoices("DEFAULT_LLM_MODEL"))
    #: Optional BYO OpenAI key. Used for chat only when no gateway key is set, and always for
    #: STT/TTS (the gateway serves text models; audio endpoints are vendor-direct).
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY"))

    # --- Knowledge: managed Dooers RAG -----------------------------------------
    #: Injected by ``dooers push`` when the organization has the RAG feature. Empty → no knowledge
    #: base; the ``search_knowledge`` tool answers that none is configured.
    dooers_rag_service_url: str = Field(default="", validation_alias=AliasChoices("DOOERS_RAG_SERVICE_URL"))
    #: ``dooers`` | ``none``. Defaults to ``dooers`` when the service URL is present.
    rag_pipeline: str = Field(default="", validation_alias=AliasChoices("RAG_PIPELINE"))

    # --- Storage for chat attachments -------------------------------------------
    store_chat_uploads: bool = Field(default=False, validation_alias=AliasChoices("STORE_CHAT_UPLOADS"))
    #: ``none`` | ``gcp`` | ``dooers`` (managed bucket injected on push with ``storage.type: dooers``).
    chat_storage_service: str = Field(default="none", validation_alias=AliasChoices("CHAT_STORAGE_SERVICE"))
    gcp_bucket_name: str = Field(default="", validation_alias=AliasChoices("GCP_BUCKET_NAME"))
    google_application_credentials: str = Field(default="", validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS"))

    # --- Platform identity / observability --------------------------------------
    agent_seed_secret: str = Field(default="", validation_alias=AliasChoices("AGENT_SEED_SECRET"))
    agent_analytics_url: str = Field(default="", validation_alias=AliasChoices("DOOERS_ANALYTICS_WEBHOOK_URL"))
    agent_core_base_url: str = Field(default="", validation_alias=AliasChoices("AGENT_CORE_BASE_URL"))
    agent_otel_service_url: str = Field(default="", validation_alias=AliasChoices("AGENT_OTEL_SERVICE_URL"))
    otel_service_name: str = Field(default="", validation_alias=AliasChoices("OTEL_SERVICE_NAME"))

    # --- Channels ----------------------------------------------------------------
    tools_whatsapp_base_url: str = Field(
        default="https://services.dooers.ai/whatsapp",
        validation_alias=AliasChoices("DOOERS_WHATSAPP_TOOLS_BASE", "TOOLS_WHATSAPP_BASE_URL"),
    )
    #: What to do with messages a human sent from the agent's own WhatsApp number to another chat:
    #: ``register`` (store as assistant, no AI), ``dispatch`` (run the handler) or ``ignore``.
    whatsapp_peer_message: str = Field(default="register", validation_alias=AliasChoices("WHATSAPP_PEER_MESSAGE"))

    # --- Multimodal ----------------------------------------------------------------
    #: Content kinds accepted on the chat. Documents (pdf, docx, xlsx, csv, txt, json) are extracted
    #: into thread context; images go to the model as vision input; audio is transcribed.
    agent_allowed_content_types: str = Field(
        default="text,audio,image,document",
        validation_alias=AliasChoices("AGENT_ALLOWED_CONTENT_TYPES", "ALLOWED_CONTENT_TYPES"),
    )

    # --- Skills -----------------------------------------------------------------------
    #: Repository folder with built-in Skills (Markdown). Studio uploads add to these.
    skills_dir: str = Field(default="skills", validation_alias=AliasChoices("SKILLS_DIR"))

    # ------------------------------------------------------------------------------
    @property
    def api_prefix(self) -> str:
        if not self.use_prefix:
            return ""
        env = self.api_environment.strip().strip("/")
        name = self.api_agent_name.strip().strip("/")
        return f"/api/{env}/{name}"

    @property
    def public_base_url(self) -> str:
        return f"{self.service_url.rstrip('/')}{self.api_prefix}"

    @property
    def uses_dooers_gateway(self) -> bool:
        return bool(self.dooers_gateway_api_key.strip())

    @property
    def gateway_base_url(self) -> str:
        raw = (self.dooers_gateway_base_url or DEFAULT_GATEWAY_BASE_URL).strip().rstrip("/")
        return raw if raw.endswith("/v1") else f"{raw}/v1"

    @property
    def resolved_rag_pipeline(self) -> str:
        explicit = (self.rag_pipeline or "").strip().lower()
        if explicit in {"dooers", "none"}:
            return explicit
        return "dooers" if self.dooers_rag_service_url.strip() else "none"


def _validate(s: Settings) -> list[str]:
    problems: list[str] = []
    if not s.uses_dooers_gateway and not s.openai_api_key.strip():
        problems.append("No LLM credential: set DOOERS_GATEWAY_API_KEY (recommended) or OPENAI_API_KEY (fallback).")
    if (s.rag_pipeline or "").strip().lower() not in {"", "dooers", "none"}:
        problems.append("RAG_PIPELINE must be 'dooers' or 'none'.")
    if s.resolved_rag_pipeline == "dooers" and not s.dooers_rag_service_url.strip():
        problems.append("RAG_PIPELINE=dooers requires DOOERS_RAG_SERVICE_URL.")
    chat_ss = (s.chat_storage_service or "none").strip().lower()
    if chat_ss not in {"none", "gcp", "dooers"}:
        problems.append("CHAT_STORAGE_SERVICE must be one of: none, gcp, dooers.")
    if chat_ss == "gcp" and not s.gcp_bucket_name.strip():
        problems.append("CHAT_STORAGE_SERVICE=gcp requires GCP_BUCKET_NAME.")
    if (s.whatsapp_peer_message or "").strip().lower() not in {"ignore", "register", "dispatch"}:
        problems.append("WHATSAPP_PEER_MESSAGE must be one of: ignore, register, dispatch.")
    db_type = (s.agent_database_type or "").strip().lower()
    if db_type == "dooers":
        if s.agent_database_host.strip().lower() in {"localhost", "127.0.0.1"}:
            print(
                "  ! AGENT_DATABASE_HOST=localhost with AGENT_DATABASE_TYPE=dooers — remove AGENT_DATABASE_* "
                "from env.prod; the platform injects the managed connection on deploy.",
                file=sys.stderr,
            )
    elif not s.agent_database_name:
        problems.append("AGENT_DATABASE_NAME is not configured.")
    return problems


settings = Settings()

_gac = settings.google_application_credentials.strip()
if _gac and (settings.agent_database_type or "").strip().lower() != "dooers":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _gac

# ``dooers.tools.rag`` reads the service URL from the process environment.
if settings.dooers_rag_service_url.strip():
    os.environ.setdefault("DOOERS_RAG_SERVICE_URL", settings.dooers_rag_service_url.strip())
# The Agents SDK trace exporter (optional) reads OPENAI_API_KEY from the environment.
if settings.openai_api_key.strip():
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key.strip())

_problems = _validate(settings)
if _problems:
    print("Configuration problems detected:", file=sys.stderr)
    for problem in _problems:
        print(f"  - {problem}", file=sys.stderr)
    if settings.config_strict:
        sys.exit(1)
    print("  -> CONFIG_STRICT is false; booting in degraded mode.", file=sys.stderr)
