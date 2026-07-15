"""Single `AgentServer` config for this service (one worker/agent per process)."""

from __future__ import annotations

from typing import Literal, cast

from dooers.agents.server import AgentConfig

from src.config import settings
from src.modules.agent.schemas import settings_schema
from src.modules.rag.knowledge_settings_hook import on_settings_updated

_raw_ca = (getattr(settings, "chat_storage_service", None) or "none").strip().lower()
_ca_storage = _raw_ca if _raw_ca in {"none", "gcp", "azure"} else "none"

# "postgres" (padrão) ou "dooers" (banco gerenciado pela Dooers, via env
# AGENT_DATABASE_TYPE). Local fica postgres; no deploy gerenciado, defina
# AGENT_DATABASE_TYPE=dooers no env.prod — ver README "Banco gerenciado".
_raw_db = (settings.agent_database_type or "postgres").strip().lower()
_db_type = cast(
    "Literal['postgres', 'cosmos', 'dooers']",
    _raw_db if _raw_db in {"postgres", "cosmos", "dooers"} else "postgres",
)

agent_config = AgentConfig(
    database_type=_db_type,
    assistant_name=settings.assistant_name,
    database_host=settings.agent_database_host,
    database_port=settings.agent_database_port,
    database_user=settings.agent_database_user,
    database_name=settings.agent_database_name,
    database_password=settings.agent_database_password,
    database_ssl=settings.agent_database_ssl,
    settings_schema=settings_schema,
    allowed_content_types=settings.agent_allowed_content_types,
    content_policy_denial_message=(
        "Por enquanto eu não processo este tipo de anexo no chat ({offenders}). "
        "Formatos aceitos neste canal: {allowed}."
    ),
    on_settings_updated=on_settings_updated,
    agent_seed_secret=settings.agent_seed_secret,
    analytics_webhook_url=settings.agent_analytics_url or None,
    store_chat_uploads=settings.store_chat_uploads,
    chat_storage_service=_ca_storage,
    gcp_storage_bucket=settings.gcp_bucket_name,
    azure_storage_connection_string=settings.azure_storage_connection_string,
    azure_storage_container=settings.azure_storage_container,
    dooers_whatsapp_service=True,
    # Optional otel/core overrides; empty → SDK platform defaults.
    agent_core_base_url=settings.agent_core_base_url.strip(),
    otel_service_url=settings.agent_otel_service_url.strip(),
    otel_service_name=settings.otel_service_name.strip(),
)
