"""
AgentServer (Dooers SDK), audio cache, and WebSocket handler.

See docs/01-anatomy.md for the full flow and extension points.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from typing import Any

from dooers import AgentSend, AgentServer, ImagePart
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

logger = logging.getLogger("dooers-starter.agent")

if app_settings.tools_whatsapp_base_url:
    os.environ.setdefault("DOOERS_WHATSAPP_TOOLS_BASE", app_settings.tools_whatsapp_base_url.strip())

agent_server = AgentServer(agent_config)


def _api_provider_wire(agent_settings: dict) -> str:
    p = normalize_llm_provider(agent_settings)
    if p in ("openai", "azure_openai"):
        return "openai_responses"
    if p == "gemini":
        return "gemini"
    if p == "claude":
        return "claude"
    return "openai_responses"


def _parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _tool_outputs_by_name(items: Iterable[dict[str, Any]]) -> list[tuple[str, Any]]:
    pending: dict[str, str] = {}
    outputs: list[tuple[str, Any]] = []
    for raw in items:
        item_type = raw.get("type")
        if item_type == "function_call":
            call_id = str(raw.get("call_id") or raw.get("id") or "")
            name = str(raw.get("name") or "tool")
            if call_id:
                pending[call_id] = name
        elif item_type == "function_call_output":
            call_id = str(raw.get("call_id") or "")
            name = pending.pop(call_id, "tool")
            outputs.append((name, _parse_jsonish(raw.get("output"))))
    return outputs


def _feedback_form_requested(items: Iterable[dict[str, Any]]) -> bool:
    for name, output in _tool_outputs_by_name(items):
        if name == "request_feedback_form" and isinstance(output, dict) and output.get("requiresForm") is True:
            return True
    return False


def _feedback_form(send: AgentSend):
    return send.form(
        "Como foi sua experiência?",
        [
            send.form_select(
                "rating",
                label="Nota",
                order=1,
                required=True,
                options=[
                    {"value": "5", "label": "Excelente"},
                    {"value": "4", "label": "Boa"},
                    {"value": "3", "label": "Regular"},
                    {"value": "2", "label": "Ruim"},
                    {"value": "1", "label": "Péssima"},
                ],
            ),
            send.form_text(
                "comment",
                label="Comentário (opcional)",
                order=2,
                required=False,
                placeholder="Conte-nos o que podemos melhorar",
            ),
        ],
        submit_label="Enviar feedback",
        cancel_label="Cancelar",
        size="medium",
    )


def _message_from_feedback_form(incoming: Any) -> str:
    form_data = getattr(incoming, "form_data", None)
    if not isinstance(form_data, dict):
        return ""
    rating = str(form_data.get("rating") or "").strip()
    comment = str(form_data.get("comment") or "").strip()
    if not rating:
        return ""
    parts = [f"Feedback recebido — nota: {rating}/5."]
    if comment:
        parts.append(f"Comentário: {comment}")
    return " ".join(parts)


async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    """Main handler: normalize content, run workflow, emit UI events."""
    agent_id = incoming.context.agent_id or ""
    agent_settings = await settings.get_all()
    agent_display_name = agent_settings.get("agent_name") or app_settings.assistant_name or "AI Agent"

    yield send.run_start(agent_id=agent_id)

    if incoming.form_cancelled:
        yield send.text("Feedback cancelado. Posso ajudar com mais alguma coisa?", author=agent_display_name)
        yield send.run_end()
        return

    form_message = _message_from_feedback_form(incoming)
    if form_message:
        incoming.message = form_message

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

    if _feedback_form_requested(out.get("new_runner_items") or []):
        yield _feedback_form(send)
        yield send.run_end()
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
