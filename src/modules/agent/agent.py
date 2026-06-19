"""
AgentServer (Dooers SDK), audio cache, and WebSocket handler.

Extends the starter with:
- Unit YES/NO WhatsApp response detection (intercepts before agent flow)
- Proactive WhatsApp dispatch via SDK agent_server.dispatch() after run_end
- AgentRunContext construction
- No feedback form (franchise agent)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from dooers.agents.server import AgentSend, AgentServer, ImagePart, User
from openai import AsyncOpenAI

from src.config import settings as app_settings
from src.modules.agent.agent_config import agent_config
from src.modules.agent.workflow import run_workflow
from src.modules.helpers.speech import generate_speech, stt_model
from src.modules.helpers.wire_content import incoming_parts_to_wire_content_dicts
from src.modules.helpers.error_messages import GENERIC_USER_ERROR_MESSAGE
from src.modules.external.openai import get_openai_audio_client
from src.modules.llm.factory import (
    UserVisibleAgentError,
    ensure_llm_provider_config,
    ensure_openai_audio_config,
    normalize_llm_provider,
)
from src.modules.services.supabase_client import get_supabase_client
from src.modules.services.treinamentos_service import (
    buscar_unidade_por_telefone,
    listar_inscricoes_por_unidade,
    registrar_resposta_presenca,
)

logger = logging.getLogger("whatsapp-franquia.agent")

if app_settings.tools_whatsapp_base_url:
    os.environ.setdefault("DOOERS_WHATSAPP_TOOLS_BASE", app_settings.tools_whatsapp_base_url.strip())

agent_server = AgentServer(agent_config)

# Normalised responses for YES/NO detection
_SIM_VARIANTS = frozenset(
    {
        "sim", "s", "yes", "y", "ok", "confirmo", "confirmado", "confirmar",
        "aceito", "aceitar", "vou", "presente", "estarei", "certo",
        "✅", "👍",
    }
)
_NAO_VARIANTS = frozenset(
    {
        "não", "nao", "n", "no", "recuso", "recusar", "cancelar", "cancelo",
        "ausente", "impossível", "impossivel",
        "❌", "👎",
    }
)


async def _dispatch_whatsapp_proactive(
    agent_id: str,
    to_phone: str,
    message: str,
    instance_id: str,
    agent_phone: str,
) -> None:
    """Fire-and-forget: send a proactive WhatsApp message via SDK dispatch."""
    try:
        stream = await agent_server.dispatch(
            dooers_agent_handler,
            agent_id,
            message=message,
            user=User(user_id=to_phone, user_name=""),
            channel="whatsapp",
            channel_meta={
                "whatsapp": {
                    "to_e164": to_phone,
                    "from_e164": to_phone,
                    "instance_id": instance_id,
                    "agent_phone_e164": agent_phone,
                },
                "_proactive_notification": message,
            },
        )
        async for _ in stream:
            pass
    except Exception:
        logger.exception("_dispatch_whatsapp_proactive failed to=%s", to_phone)


def _api_provider_wire(agent_settings: dict) -> str:
    p = normalize_llm_provider(agent_settings)
    if p in ("openai", "azure_openai"):
        return "openai_responses"
    if p == "gemini":
        return "gemini"
    if p == "claude":
        return "claude"
    return "openai_responses"


def _get_whatsapp_meta(incoming: Any) -> dict:
    """Extract the whatsapp sub-dict from channel_meta passed by whatsapp_channel.py."""
    channel_meta = getattr(incoming.context, "channel_meta", None) or {}
    if isinstance(channel_meta, dict):
        return channel_meta.get("whatsapp") or {}
    return {}


def _is_whatsapp_channel(incoming: Any) -> bool:
    """Return True if this message arrived via the WhatsApp channel."""
    # Primary: channel attribute set by dispatch()
    channel = getattr(incoming.context, "channel", None) or ""
    if str(channel).lower() == "whatsapp":
        return True
    # Fallback: channel_meta contains 'whatsapp' key
    return bool(_get_whatsapp_meta(incoming))


def _get_whatsapp_sender_phone(incoming: Any) -> str:
    """Extract sender E.164 phone from WhatsApp channel_meta (set by whatsapp_channel.py)."""
    meta = _get_whatsapp_meta(incoming)
    return str(meta.get("from_e164") or "").strip()


def _normalizar_telefone(phone: str) -> str:
    """Strip all non-digit characters, keep leading + if present."""
    if not phone:
        return ""
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)


def _detectar_resposta_unidade(text: str) -> str | None:
    """Return 'sim', 'nao', or None based on message text."""
    normalised = text.strip().lower().rstrip(".,!?;:")
    if normalised in _SIM_VARIANTS:
        return "sim"
    if normalised in _NAO_VARIANTS:
        return "nao"
    return None


async def _try_handle_unit_response(
    incoming: Any,
    analytics: Any,
) -> tuple[bool, str]:
    """
    Try to interpret message as a franchise unit YES/NO response.

    Returns (handled: bool, reply_text: str).
    handled=True means we consumed the message and reply_text is the response to send.
    handled=False means normal agent flow should continue.
    """
    if not _is_whatsapp_channel(incoming):
        return False, ""

    message_text = (incoming.message or "").strip()
    if not message_text:
        return False, ""

    resposta = _detectar_resposta_unidade(message_text)
    if resposta is None:
        return False, ""

    sender_phone_raw = _get_whatsapp_sender_phone(incoming)
    if not sender_phone_raw:
        return False, ""

    sender_phone = _normalizar_telefone(sender_phone_raw)

    try:
        supabase = await get_supabase_client()
        unidade = await buscar_unidade_por_telefone(supabase, sender_phone)
        if not unidade:
            return False, ""

        unidade_id = unidade.get("id") or ""
        unidade_nome = unidade.get("nome") or sender_phone

        inscricoes = await listar_inscricoes_por_unidade(supabase, unidade_id, apenas_pendentes=True)
        if not inscricoes:
            return False, ""

        # Use the most recent pending inscription
        inscricao = inscricoes[0]
        inscricao_id = inscricao.get("id") or ""
        treinamento_id = inscricao.get("cronograma_id") or ""

        ok = await registrar_resposta_presenca(supabase, inscricao_id, resposta)

        if ok:
            await analytics.track(
                "unit.attendance_response",
                data={
                    "unidade_id": unidade_id,
                    "treinamento_id": treinamento_id,
                    "resposta": resposta,
                },
            )
            if resposta == "sim":
                reply = f"✅ Presença confirmada! Obrigado, *{unidade_nome}*. Até o treinamento!"
            else:
                reply = f"❌ Ausência registrada. Obrigado pelo retorno, *{unidade_nome}*."
            return True, reply
        else:
            return False, ""

    except Exception:
        logger.exception("_try_handle_unit_response falhou sender=%s", sender_phone_raw)
        return False, ""


async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    """Main handler: normalize content, intercept unit YES/NO, run workflow, emit UI events."""
    agent_id = incoming.context.agent_id or ""
    agent_settings = await settings.get_all()
    agent_display_name = agent_settings.get("agent_name") or app_settings.assistant_name or "Assistente"

    yield send.run_start(agent_id=agent_id)

    # --- Proactive outbound dispatch: echo message directly, skip LLM ---
    _ch_meta = getattr(incoming.context, "channel_meta", None) or {}
    if isinstance(_ch_meta, dict) and "_proactive_notification" in _ch_meta:
        notification_text = str(_ch_meta.get("_proactive_notification") or "").strip()
        if notification_text:
            yield send.text(notification_text, author=agent_display_name)
        yield send.run_end()
        return

    if incoming.form_cancelled:
        yield send.text("Operação cancelada. Posso ajudar com mais alguma coisa?", author=agent_display_name)
        yield send.run_end()
        return

    try:
        ensure_llm_provider_config(agent_settings)
        ensure_openai_audio_config(agent_settings)
    except UserVisibleAgentError as e:
        yield send.text(str(e), author=agent_display_name)
        yield send.run_end(status="failed", error="configuration")
        return
    except Exception:
        logger.exception("LLM/openai settings validation failed")
        yield send.text(GENERIC_USER_ERROR_MESSAGE, author=agent_display_name)
        yield send.run_end(status="failed", error="configuration_error")
        return

    # --- Unit YES/NO WhatsApp interception ---
    unit_handled, unit_reply = await _try_handle_unit_response(incoming, analytics)
    if unit_handled:
        yield send.text(unit_reply, author=agent_display_name)
        yield send.run_end()
        return

    # --- Normal content processing ---
    content_parts = incoming.content or []
    oai: AsyncOpenAI = get_openai_audio_client(agent_settings)

    transcripts: list[str] = []
    image_parts: list[tuple[bytes, str | None, str | None, str | None]] = []
    doc_notes: list[str] = []
    for part in content_parts:
        if not hasattr(part, "type"):
            continue
        if part.type == "audio":
            model = stt_model(agent_settings)
            try:
                tr = await oai.audio.transcriptions.create(
                    model=model,
                    file=(part.filename or "audio.webm", part.data, part.mime_type),
                )
                transcripts.append(tr.text)
                await analytics.track("stt.transcribed", data={"model": model})
            except Exception:
                logger.exception("STT failed")
                await analytics.track("error.occurred", data={"stage": "stt"})
        elif part.type == "image":
            fname = getattr(part, "filename", None) or "image"
            data = getattr(part, "data", None) or b""
            raw_url = getattr(part, "url", None)
            url = raw_url.strip() if isinstance(raw_url, str) else None
            if url == "":
                url = None
            if data or url:
                image_parts.append((data, getattr(part, "mime_type", None), fname, url))
            else:
                doc_notes.append(f"[Imagem: {fname}]")

    text_segments: list[str] = []
    if incoming.message:
        text_segments.append(incoming.message)
    if transcripts:
        ttext = "\n".join(transcripts)
        transcript_labeled = f"Audio Translation: {ttext}"
        text_segments.append(transcript_labeled)
        wire_parts = incoming_parts_to_wire_content_dicts(content_parts)
        wire_parts.append({"type": "text", "text": transcript_labeled})
        yield send.update_user_event(
            event_id=incoming.context.event_id,
            content=wire_parts,
        )
    if doc_notes:
        text_segments.append("\n".join(doc_notes))

    text_for_llm = "\n".join(text_segments).strip()

    if not text_for_llm.strip() and not image_parts:
        yield send.text("Envie uma mensagem de texto ou áudio.", author=agent_display_name)
        yield send.run_end()
        return

    incoming.message = text_for_llm
    incoming.content = [
        ImagePart(
            data=d,
            mime_type=m or "image/jpeg",
            filename=fname or "image",
            url=u,
        )
        for d, m, fname, u in image_parts
    ]

    try:
        out = await run_workflow(
            incoming=incoming,
            send=send,
            memory=memory,
            analytics=analytics,
            agent_settings=agent_settings,
            api_provider=_api_provider_wire(agent_settings),
        )
    except ValueError as e:
        yield send.text(str(e), author=agent_display_name)
        yield send.run_end(status="failed", error="unsupported_input")
        return
    except UserVisibleAgentError as e:
        yield send.text(str(e), author=agent_display_name)
        yield send.run_end(status="failed", error="user_message")
        return
    except Exception as e:
        logger.exception("run_workflow failed")
        await analytics.track(
            "error.occurred",
            data={"error_type": type(e).__name__, "stage": "workflow"},
        )
        yield send.text(GENERIC_USER_ERROR_MESSAGE, author=agent_display_name)
        yield send.run_end(status="failed", error="workflow_failed")
        return

    reply = (out.get("reply") or "").strip()
    if not reply:
        reply = "Sem resposta do modelo."

    yield send.text(reply, author=agent_display_name)

    mode = (agent_settings.get("reply_mode") or "text").strip().lower()
    if mode in ("voz", "ambos", "voice", "both"):
        try:
            url, mime = await generate_speech(reply, agent_settings=agent_settings)
            yield send.audio(url=url, mime_type=mime, author=agent_display_name)
        except Exception:
            logger.exception("TTS failed")
            await analytics.track("error.occurred", data={"stage": "tts"})

    yield send.run_end()

    # --- Dispatch pending WhatsApp sends accumulated by tools during Runner.run() ---
    pending_sends = out.get("pending_whatsapp_sends") or []
    if pending_sends:
        whatsapp_meta = _get_whatsapp_meta(incoming)
        instance_id = str(whatsapp_meta.get("instance_id") or "").strip()
        agent_phone = str(whatsapp_meta.get("agent_phone_e164") or "").strip()
        for spec in pending_sends:
            to_phone = str(spec.get("to_phone") or "").strip()
            message = str(spec.get("message") or "").strip()
            if to_phone and message:
                asyncio.create_task(
                    _dispatch_whatsapp_proactive(
                        agent_id=agent_id,
                        to_phone=to_phone,
                        message=message,
                        instance_id=instance_id,
                        agent_phone=agent_phone,
                    )
                )
