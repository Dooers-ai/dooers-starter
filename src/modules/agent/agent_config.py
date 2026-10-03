"""Single `AgentServer` config for this service (one agent per process)."""

from __future__ import annotations

from typing import Literal, cast

from dooers.agents.server import AgentConfig

from src.config import settings
from src.modules.agent.schemas import settings_schema
from src.modules.rag.knowledge_settings_hook import on_settings_updated

_raw_storage = (settings.chat_storage_service or "none").strip().lower()
_chat_storage = cast(
    "Literal['none', 'gcp', 'dooers']",
    _raw_storage if _raw_storage in {"none", "gcp", "dooers"} else "none",
)

# "postgres" for local development; "dooers" for the managed database on the hosted runtime
# (AGENT_DATABASE_TYPE=dooers in env.prod). See README "Banco de dados".
_raw_db = (settings.agent_database_type or "postgres").strip().lower()
_db_type = cast(
    "Literal['postgres', 'dooers']",
    _raw_db if _raw_db in {"postgres", "dooers"} else "postgres",
)

_raw_peer = (settings.whatsapp_peer_message or "register").strip().lower()
_peer_policy = cast(
    "Literal['ignore', 'register', 'dispatch']",
    _raw_peer if _raw_peer in {"ignore", "register", "dispatch"} else "register",
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
        "Por enquanto eu não processo este tipo de anexo no chat ({offenders}). Formatos aceitos neste canal: {allowed}."
    ),
    on_settings_updated=on_settings_updated,
    agent_seed_secret=settings.agent_seed_secret,
    analytics_webhook_url=settings.agent_analytics_url or None,
    store_chat_uploads=settings.store_chat_uploads,
    chat_storage_service=_chat_storage,
    gcp_storage_bucket=settings.gcp_bucket_name,
    dooers_whatsapp_service=True,
    whatsapp_peer_message=_peer_policy,
    # Optional overrides; empty → SDK platform defaults.
    agent_core_base_url=settings.agent_core_base_url.strip(),
    otel_service_url=settings.agent_otel_service_url.strip(),
    otel_service_name=settings.otel_service_name.strip(),
)
