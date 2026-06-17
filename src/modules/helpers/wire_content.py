"""Map handler ContentPart objects to wire (S2C) dicts for `send.update_user_event`."""


def incoming_parts_to_wire_content_dicts(parts) -> list[dict]:
    """Rebuild persisted-style content (metadata only, no binary) from `incoming.content`."""
    out: list[dict] = []
    for part in parts:
        if not hasattr(part, "type"):
            continue
        t = part.type
        if t == "text":
            out.append({"type": "text", "text": getattr(part, "text", "")})
        elif t == "audio":
            d: dict = {"type": "audio"}
            for key in ("url", "mime_type", "duration", "filename", "ref_id"):
                val = getattr(part, key, None)
                if val is not None:
                    d[key] = val
            out.append(d)
        elif t == "image":
            d = {"type": "image"}
            for key in ("url", "mime_type", "width", "height", "alt", "filename", "ref_id"):
                val = getattr(part, key, None)
                if val is not None:
                    d[key] = val
            out.append(d)
        elif t == "document":
            d = {"type": "document"}
            for key in ("url", "mime_type", "filename", "size_bytes", "ref_id"):
                val = getattr(part, key, None)
                if val is not None:
                    d[key] = val
            out.append(d)
    return out
