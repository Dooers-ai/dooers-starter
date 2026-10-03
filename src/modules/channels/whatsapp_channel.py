"""Dispatch / register for inbound Dooers tools-whatsapp (outbound and HMAC live in the SDK)."""

from __future__ import annotations

from typing import Any

from dooers.agents.server import User, normalize_e164, whatsapp_thread_id
from fastapi import HTTPException


def _peer_policy(agent_server: Any) -> str:
    cfg = getattr(agent_server, "_config", None)
    raw = getattr(cfg, "whatsapp_peer_message", None) if cfg is not None else None
    policy = str(raw or "register").strip().lower()
    if policy not in {"ignore", "register", "dispatch"}:
        return "register"
    return policy


async def dispatch_tools_whatsapp_inbound(
    agent_server: Any,
    agent_handler: Any,
    body_json: dict[str, Any],
) -> str | None:
    """Handle inbound from dooers-tools-whatsapp.

    - Customer / self-chat → full ``dispatch`` (AI may reply).
    - Peer ``fromMe`` (human on phone, other chat) → ``whatsapp_peer_message`` policy.
    Returns thread_id, or None when ignored.
    """
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

    from_me = bool(body_json.get("from_me"))
    self_chat = bool(body_json.get("self_chat"))
    is_peer = from_me and not self_chat

    if is_peer:
        policy = _peer_policy(agent_server)
        if policy == "ignore":
            return None

    thread_id = whatsapp_thread_id(e164, instance_id=instance_id)
    user = User(
        user_id=e164,
        user_name=(body_json.get("user_name") or "").strip() or e164,
        user_email=f"whatsapp_user:{e164}",
        user_mobile_number=e164,
        user_whatsapp_number=e164,
    )
    content = body_json.get("content")
    channel_meta = {
        "whatsapp": {
            "from_e164": e164,
            "to_e164": to_e164,
            "agent_phone_e164": agent_phone_e164,
            "instance_id": body_json.get("instance_id") or "",
            "from_me": from_me,
            "self_chat": self_chat,
            "wa_message_id": body_json.get("wa_message_id") or "",
        }
    }
    agent_id = body_json.get("agent_id") or ""
    org = body_json.get("organization_id") or ""
    ws = body_json.get("workspace_id") or ""
    message = body_json.get("message") or ""

    if is_peer and _peer_policy(agent_server) == "register":
        author = (body_json.get("user_name") or "").strip() or "WhatsApp"
        return await agent_server.ingest(
            agent_id,
            message=message,
            user=user,
            organization_id=org,
            workspace_id=ws,
            thread_id=thread_id,
            content=content,
            channel="whatsapp",
            channel_meta=channel_meta,
            actor="assistant",
            author=author,
            data={"whatsapp_peer": True},
        )

    stream = await agent_server.dispatch(
        agent_handler,
        agent_id,
        message=message,
        user=user,
        organization_id=org,
        workspace_id=ws,
        thread_id=thread_id,
        content=content,
        channel="whatsapp",
        channel_meta=channel_meta,
    )
    async for _ in stream:
        pass
    return stream.thread_id
