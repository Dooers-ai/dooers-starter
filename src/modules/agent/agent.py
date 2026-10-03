"""AgentServer instance and the WebSocket/WhatsApp handler.

Flow per turn: ``run_start`` → validate config → normalize inputs (audio→text, documents→processed,
images kept for vision) → stream the workflow (reasoning/tool events) → final text (+ optional
voice) → ``run_end``. See docs/01-anatomy.md.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dooers.agents.server import AgentSend, AgentServer, ImagePart, apply_chat_llm_override

from src.config import settings as app_settings
from src.modules.agent.agent_config import agent_config
from src.modules.agent.schemas import settings_schema
from src.modules.agent.workflow import WorkflowOutcome, run_workflow
from src.modules.doc_processing.prompt_context import summarize_document_for_note
from src.modules.doc_processing.service import process_document_part
from src.modules.helpers.chart_demo import handle_chart_test, is_chart_test_command
from src.modules.helpers.error_messages import GENERIC_USER_ERROR_MESSAGE
from src.modules.helpers.speech import generate_speech, transcribe
from src.modules.helpers.wire_content import incoming_parts_to_wire_content_dicts
from src.modules.llm.factory import UserVisibleAgentError, ensure_llm_provider_config
from src.modules.llm.gateway_models import maybe_refresh_schema_llm_models_background
from src.modules.observability.soft_failures import record_soft_failure

logger = logging.getLogger("dooers-starter.agent")

if app_settings.tools_whatsapp_base_url:
    os.environ.setdefault("DOOERS_WHATSAPP_TOOLS_BASE", app_settings.tools_whatsapp_base_url.strip())

agent_server = AgentServer(agent_config)


def form_data_to_text(form_data: dict[str, Any] | None) -> str:
    """Generic form submission → one line the model can read. Override for custom forms."""
    if not isinstance(form_data, dict) or not form_data:
        return ""
    pairs = [f"{k}: {v}" for k, v in form_data.items() if str(v or "").strip()]
    return "Formulário enviado — " + "; ".join(pairs) if pairs else ""


async def dooers_agent_handler(incoming, send: AgentSend, memory, analytics, settings):
    agent_id = incoming.context.agent_id or ""
    agent_settings = apply_chat_llm_override(
        await settings.get_all(),
        chat_context=getattr(incoming.context, "chat_context", None),
        schema=getattr(settings, "schema", None),
    )
    author = str(agent_settings.get("agent_name") or app_settings.assistant_name or "AI Agent")

    yield send.run_start(agent_id=agent_id)
    await maybe_refresh_schema_llm_models_background(settings_schema)

    if is_chart_test_command(incoming.message or ""):
        async for event in handle_chart_test(incoming.message or "", send):
            yield event
        yield send.run_end()
        return

    if incoming.form_cancelled:
        yield send.text("Formulário cancelado. Posso ajudar com mais alguma coisa?", author=author)
        yield send.run_end()
        return
    form_text = form_data_to_text(incoming.form_data)
    if form_text:
        incoming.message = form_text

    try:
        ensure_llm_provider_config(agent_settings)
    except UserVisibleAgentError as exc:
        yield send.text(str(exc), author=author)
        yield send.run_end(status="failed", error="configuration")
        return

    # --- normalize multimodal input -------------------------------------------------------
    transcripts: list[str] = []
    notes: list[str] = []
    images: list[ImagePart] = []
    for part in incoming.content or []:
        kind = getattr(part, "type", None)
        if kind == "audio":
            try:
                transcripts.append(
                    await transcribe(
                        data=part.data, filename=part.filename or "audio.webm", mime_type=part.mime_type, agent_settings=agent_settings
                    )
                )
                await analytics.track("stt.transcribed", data={"agent_id": agent_id})
            except UserVisibleAgentError as exc:
                yield send.text(str(exc), author=author)
                yield send.run_end(status="failed", error="stt_configuration")
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("STT failed")
                record_soft_failure("stt", "transcribe", exc, agent_id=agent_id)
                notes.append("[Áudio recebido, mas a transcrição falhou.]")
        elif kind == "image":
            url = (getattr(part, "url", None) or "").strip() or None
            data = getattr(part, "data", None) or b""
            if data or url:
                images.append(ImagePart(data=data, mime_type=part.mime_type or "image/jpeg", filename=part.filename or "image", url=url))
            else:
                notes.append(f"[Imagem: {part.filename or 'image'}]")
        elif kind == "document":
            processed = await process_document_part(
                agent_id=agent_id, thread_id=incoming.context.thread_id, event_id=incoming.context.event_id, part=part
            )
            await analytics.track("document.processed", data={"agent_id": agent_id, "status": processed.status})
            notes.append(summarize_document_for_note(processed))

    segments: list[str] = []
    if incoming.message:
        segments.append(incoming.message)
    if transcripts:
        labeled = "Audio Translation: " + "\n".join(transcripts)
        segments.append(labeled)
        wire_parts = incoming_parts_to_wire_content_dicts(incoming.content or [])
        wire_parts.append({"type": "text", "text": labeled})
        yield send.update_user_event(event_id=incoming.context.event_id, content=wire_parts)
    if notes:
        segments.append("\n".join(notes))

    incoming.message = "\n".join(segments).strip()
    incoming.content = images
    if not incoming.message and not images:
        yield send.text("Envie uma mensagem de texto, áudio, imagem ou documento.", author=author)
        yield send.run_end()
        return

    # --- run ------------------------------------------------------------------------------
    outcome: WorkflowOutcome | None = None
    try:
        async for event in run_workflow(
            incoming=incoming, send=send, memory=memory, analytics=analytics, agent_settings=agent_settings, author=author
        ):
            if isinstance(event, WorkflowOutcome):
                outcome = event
            else:
                yield event
    except UserVisibleAgentError as exc:
        yield send.text(str(exc), author=author)
        yield send.run_end(status="failed", error="user_message")
        return
    except ValueError as exc:
        yield send.text(str(exc), author=author)
        yield send.run_end(status="failed", error="unsupported_input")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("workflow failed")
        await analytics.track("error.occurred", data={"error_type": type(exc).__name__, "stage": "workflow"})
        yield send.text(GENERIC_USER_ERROR_MESSAGE, author=author)
        yield send.run_end(status="failed", error="workflow_failed")
        return

    if outcome is None:
        yield send.text(GENERIC_USER_ERROR_MESSAGE, author=author)
        yield send.run_end(status="failed", error="no_outcome")
        return

    for name in outcome.tools_called:
        await analytics.track("tool.called", data={"agent_id": agent_id, "tool": name})
    for skill_id in outcome.skills_loaded:
        await analytics.track("skill.loaded", data={"agent_id": agent_id, "skill": skill_id})

    reply = outcome.reply or "Sem resposta do modelo."
    yield send.text(reply, author=author)

    if outcome.status == "ok":
        mode = str(agent_settings.get("reply_mode") or "text").strip().lower()
        if mode in {"voz", "ambos", "voice", "both"}:
            try:
                url, mime = await generate_speech(reply, agent_settings=agent_settings)
                yield send.audio(url=url, mime_type=mime, author=author)
            except Exception as exc:  # noqa: BLE001
                logger.exception("TTS failed")
                record_soft_failure("tts", "generate_speech", exc, agent_id=agent_id)

    if outcome.status.startswith("guard_"):
        # A policy block is a legitimate outcome, not a system failure.
        await analytics.track("guardrail.blocked", data={"agent_id": agent_id, "phase": outcome.status})
        yield send.run_end()
    elif outcome.status == "ok":
        yield send.run_end()
    else:
        yield send.run_end(status="failed", error=outcome.status)
