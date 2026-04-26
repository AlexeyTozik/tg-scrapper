from datetime import datetime
from typing import Any


def make_json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [make_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def serialize_message(msg: Any, channel_name: str | None = None) -> dict[str, Any]:
    return {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.message,
        "raw_text": msg.raw_text,
        "sender_id": msg.sender_id,
        "chat_id": msg.chat_id,
        "channel_name": channel_name,
        "views": getattr(msg, "views", None),
        "forwards": getattr(msg, "forwards", None),
        "replies": getattr(getattr(msg, "replies", None), "replies", None),
        "reply_to_msg_id": getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None),
        "post_author": getattr(msg, "post_author", None),
        "grouped_id": getattr(msg, "grouped_id", None),
        "has_media": msg.media is not None,
        "action_type": type(msg.action).__name__ if getattr(msg, "action", None) else None,
        "action": make_json_safe(msg.action.to_dict()) if getattr(msg, "action", None) else None,
        "media_type": type(msg.media).__name__ if getattr(msg, "media", None) else None,
        "buttons": bool(getattr(msg, "buttons", None)),
    }
