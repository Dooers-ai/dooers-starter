import os
import sys

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    http_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("HTTP_PORT", "PORT"),
    )
    use_prefix: bool = Field(
        default=True,
        validation_alias=AliasChoices("USE_API_PREFIX"),
    )
    api_environment: str = "dev"
    api_agent_name: str = "dooers-starter"
    #: Root log level for the process (DEBUG, INFO, WARNING, …). Azure SDK / httpx stay at WARNING — see ``src.main.configure_logging``.
    logging_level: str = Field(default="INFO", validation_alias=AliasChoices("LOGGING_LEVEL"))

    agent_database_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("AGENT_DATABASE_HOST"),
    )
    agent_database_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("AGENT_DATABASE_PORT"),
    )
    agent_database_user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("AGENT_DATABASE_USER"),
    )
    agent_database_name: str = Field(
        default="dooers_agent",
        validation_alias=AliasChoices("AGENT_DATABASE_NAME"),
    )
    agent_database_password: str = Field(
        default="",
        validation_alias=AliasChoices("AGENT_DATABASE_PASSWORD"),
    )
    agent_database_ssl: bool | str = Field(
        default=False,
        validation_alias=AliasChoices("AGENT_DATABASE_SSL"),
    )

    # Required for RAG (Vector Store + OpenAI file ingest). Not user-configurable.
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY"))
    rag_pipeline: str = Field(
        default="openai",
        validation_alias=AliasChoices("RAG_PIPELINE"),
    )
    azure_ai_search_endpoint: str = Field(default="", validation_alias=AliasChoices("AZURE_AI_SEARCH_ENDPOINT"))
    azure_ai_search_api_key: str = Field(default="", validation_alias=AliasChoices("AZURE_AI_SEARCH_API_KEY"))
    azure_ai_search_index_prefix: str = Field(
        default="dooers-kb",
        validation_alias=AliasChoices("AZURE_AI_SEARCH_INDEX_PREFIX"),
    )
    #: After upload, GET the document once to prove it exists (helps debug stale portal UX).
    azure_ai_search_verify_read_after_write: bool = Field(
        default=False,
        validation_alias=AliasChoices("AZURE_AI_SEARCH_VERIFY_READ_AFTER_WRITE"),
    )
    azure_storage_connection_string: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_STORAGE_CONNECTION_STRING"),
    )
    azure_storage_container: str = Field(default="", validation_alias=AliasChoices("AZURE_STORAGE_CONTAINER"))
    #: When True, archive RAG upload originals to blob (``upload_archive_bytes``). Requires ``RAG_STORAGE_SERVICE`` = gcp|azure.
    store_rag_uploads: bool = Field(default=False, validation_alias=AliasChoices("STORE_RAG_UPLOADS"))
    rag_storage_service: str = Field(
        default="none",
        validation_alias=AliasChoices("RAG_STORAGE_SERVICE"),
    )

    gcp_bucket_name: str = Field(default="", validation_alias=AliasChoices("GCP_BUCKET_NAME"))

    #: When True, chat attachments may be written to object storage when the creator enables ``persist_chat_attachments``.
    #: Requires ``CHAT_STORAGE_SERVICE`` = gcp|azure and credentials.
    store_chat_uploads: bool = Field(default=False, validation_alias=AliasChoices("STORE_CHAT_UPLOADS"))
    #: Chat blob backend: ``none`` | ``gcp`` | ``azure`` (no ``auto`` — set explicitly).
    chat_storage_service: str = Field(default="none", validation_alias=AliasChoices("CHAT_STORAGE_SERVICE"))

    # Path to service account JSON; exported to os.environ for google-cloud-* (ADC).
    google_application_credentials: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS"),
    )

    agent_analytics_url: str = Field(
        default="https://api-v2.dev.dooers.ai/api/v2/webhooks/analytics",
        validation_alias=AliasChoices("DOOERS_ANALYTICS_WEBHOOK_URL"),
    )
    service_url: str = Field(default="https://agent-dooers.ngrok.app", validation_alias=AliasChoices("SERVICE_URL"))
    agent_seed_secret: str = Field(default="", validation_alias=AliasChoices("AGENT_SEED_SECRET"))
    #: Overrides SDK default tools URL for ``dooers_whatsapp_service`` outbound.
    #: Can include path prefix (e.g. https://services.dooers.ai/whatsapp).
    tools_whatsapp_base_url: str = Field(
        default="https://services.dooers.ai/whatsapp",
        validation_alias=AliasChoices(
            "DOOERS_WHATSAPP_TOOLS_BASE", "TOOLS_WHATSAPP_BASE_URL", "tools_whatsapp_base_url"
        ),
    )
    #: Passed to ``AgentConfig.allowed_content_types`` — SDK rejects other kinds before persisting the user message.
    #: Default ``text,audio,image`` matches previous template behaviour (no chat documents).
    #: Add ``document`` (e.g. ``text,audio,image,document``) to allow file parts. To disable the allowlist, set
    #: ``allowed_content_types=None`` in ``agent_config.py``.
    agent_allowed_content_types: str = Field(
        default="text,audio,image",
        validation_alias=AliasChoices("AGENT_ALLOWED_CONTENT_TYPES", "ALLOWED_CONTENT_TYPES"),
    )

    assistant_name: str = Field(default="Assistant", validation_alias=AliasChoices("ASSISTANT_NAME"))

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


def _validate(s: Settings) -> None:
    errors: list[str] = []
    rag = (s.rag_pipeline or "").strip().lower()
    if rag not in {"openai", "azure_ai_search"}:
        errors.append("RAG_PIPELINE must be one of: openai, azure_ai_search")
    if rag == "openai" and not s.openai_api_key:
        errors.append("OPENAI_API_KEY is required when RAG_PIPELINE=openai")
    # azure_ai_search: credentials may live in agent settings (Documentos RAG); env vars are optional fallback.
    archive = (s.rag_storage_service or "none").strip().lower()
    if archive not in {"none", "gcp", "azure"}:
        errors.append("RAG_STORAGE_SERVICE must be one of: none, gcp, azure")
    chat_ss = (s.chat_storage_service or "none").strip().lower()
    if chat_ss not in {"none", "gcp", "azure"}:
        errors.append("CHAT_STORAGE_SERVICE must be one of: none, gcp, azure")
    gcp_configured = bool((s.gcp_bucket_name or "").strip())
    azure_configured = bool((s.azure_storage_connection_string or "").strip() and (s.azure_storage_container or "").strip())
    if s.store_rag_uploads and archive == "none":
        errors.append("STORE_RAG_UPLOADS=true requires RAG_STORAGE_SERVICE to be gcp or azure")
    if archive == "gcp" and not gcp_configured:
        errors.append("RAG_STORAGE_SERVICE='gcp' requires GCP_BUCKET_NAME")
    if archive == "azure" and not azure_configured:
        errors.append(
            "RAG_STORAGE_SERVICE='azure' requires AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER"
        )
    if not s.agent_database_name:
        errors.append("AGENT_DATABASE_NAME is not configured")
    if errors:
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)


settings = Settings()
if settings.google_application_credentials.strip():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials.strip()
_validate(settings)

# OpenAI Agents SDK trace export reads os.environ["OPENAI_API_KEY"] (not Pydantic's settings alone).
if settings.openai_api_key.strip():
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key.strip())
