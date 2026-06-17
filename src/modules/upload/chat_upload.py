"""Shared logic for POST /uploads (chat/form attachments).

Staging and durable chat blobs are handled by :meth:`dooers.server.AgentServer.chat_upload`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException

from src.modules.agent.agent import agent_server

# Match :class:`~dooers.config.AgentConfig` / :attr:`dooers.server.AgentServer.upload_max_size_bytes`.
MAX_UPLOAD_BYTES = agent_server.upload_max_size_bytes


async def process_chat_upload_bytes(
    *,
    data: bytes,
    filename: str,
    mime_type: str,
    agent_id: str,
    thread_id: str | None,
    run_id: str | None,
    source: Literal["chat", "form"],
) -> dict:
    """Register bytes for WebSocket ``ref_id``; durable storage when creator + ops + backend allow."""
    aid = agent_id.strip()
    if not aid:
        raise HTTPException(400, "agent_id is required")
    if not data:
        raise HTTPException(400, "empty file")

    try:
        return await agent_server.chat_upload(
            data=data,
            filename=filename,
            mime_type=mime_type,
            agent_id=aid,
            thread_id=thread_id,
            source=source,
            run_id=run_id,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
