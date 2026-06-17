"""Dispatch for inbound Dooers tools-whatsapp (outbound and HMAC live in the ``dooers`` SDK)."""

from __future__ import annotations

from typing import Any

from dooers import User, normalize_e164, whatsapp_thread_id
from fastapi import HTTPException


async def dispatch_tools_whatsapp_inbound(
    agent_server: Any,
    agent_handler: Any,
    body_json: dict[str, Any],
) -> str:
    """Run handler for an inbound message from dooers-tools-whatsapp. Returns thread_id."""
    user_raw = (body_json.get("user_id") or "").strip()
    e164 = normalize_e164(user_raw)
    to_e164_raw = (body_json.get("to_e164") or "").strip()
    to_e164 = normalize_e164(to_e164_raw) if to_e164_raw else e164
    agent_phone_raw = (body_json.get("agent_phone_e164") or "").strip()
    agent_phone_e164 = normalize_e164(agent_phone_raw) if agent_phone_raw else ""
    instance_id = (body_json.get("instance_id") or "").strip()
    if not instance_id:
        raise HTTPException(
            status_code=400,
            detail="instance_id is required (tools-whatsapp must send instance id for thread routing)",
        )
    thread_id = whatsapp_thread_id(e164, instance_id=instance_id)
    user = User(
        user_id=e164,
        user_name=(body_json.get("user_name") or "").strip() or e164,
        user_email=f"whatsapp_user:{e164}",
        user_mobile_number=e164,
        user_whatsapp_number=e164,
    )
    content = body_json.get("content")
    stream = await agent_server.dispatch(
        agent_handler,
        body_json.get("agent_id") or "",
        message=body_json.get("message") or "",
        user=user,
        organization_id=body_json.get("organization_id") or "",
        workspace_id=body_json.get("workspace_id") or "",
        thread_id=thread_id,
        content=content,
        channel="whatsapp",
        channel_meta={
            "whatsapp": {
                "from_e164": e164,
                "to_e164": to_e164,
                "agent_phone_e164": agent_phone_e164,
                "instance_id": body_json.get("instance_id") or "",
            }
        },
    )
    async for _ in stream:
        pass
    return stream.thread_id
