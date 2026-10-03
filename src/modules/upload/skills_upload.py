"""/skills-upload — validate a Skill Markdown file before Studio stores it in settings."""

from __future__ import annotations

import hashlib
import os
import uuid

from fastapi import HTTPException

from src.modules.agent.core.skills import parse_skill_markdown

MAX_SKILL_BYTES = 64 * 1024
_ALLOWED_EXTENSIONS = {".md", ".markdown"}


def process_skill_upload_bytes(*, data: bytes, filename: str, mime_type: str | None, agent_id: str) -> dict:
    """Skills are configuration, not RAG documents: the payload returned here is what FILE_MULTI persists."""
    if not (agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Skills devem ser arquivos Markdown (.md ou .markdown).")
    if not data:
        raise HTTPException(status_code=400, detail="Skill vazio.")
    if len(data) > MAX_SKILL_BYTES:
        raise HTTPException(status_code=413, detail=f"Skill excede {MAX_SKILL_BYTES} bytes.")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Skill Markdown deve estar em UTF-8.") from exc
    if "\x00" in content or not content.strip():
        raise HTTPException(status_code=400, detail="Skill Markdown inválido ou vazio.")
    try:
        spec = parse_skill_markdown(content, filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": str(uuid.uuid4()),
        "skill_id": spec.id,
        "name": spec.name,
        "description": spec.description,
        "requires_tools": list(spec.required_tools),
        "filename": filename,
        "mime_type": mime_type or "text/markdown",
        "size": len(data),
        "content_hash": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content.strip(),
        "kind": "skill",
    }
