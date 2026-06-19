"""Runtime context dataclass passed to all agent tools via RunContextWrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from supabase import AsyncClient


@dataclass
class AgentRunContext:
    supabase: AsyncClient
    openai_api_key: str
    agent_id: str
    whatsapp_instance_id: str
    agent_phone_e164: str
    gestor_phone: str
    link_avaliacao_comportamental: str = ""
    nome_agente: str = "Assistente"
    agent_settings: dict[str, Any] = field(default_factory=dict)
    # Accumulated during Runner.run(); flushed by agent.py after run_end via SDK dispatch
    pending_whatsapp_sends: list[dict] = field(default_factory=list)
