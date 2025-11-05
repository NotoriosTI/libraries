from datetime import datetime, timezone
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, Request

from src.adapters.base_db_adapter import BaseDBAdapter
from src.dependencies import get_db_adapter
from src.models.message import Message

router = APIRouter(tags=["messages"])


@router.post("/webhook/chatwoot")
async def receive_chatwoot_webhook(
    request: Request, db: BaseDBAdapter = Depends(get_db_adapter)
) -> dict:
    """
    Persist incoming Chatwoot webhook payloads or legacy mock messages.
    """

    payload = await request.json()
    print(f"[Webhook] Raw payload: {payload}")

    messages = _extract_messages_from_payload(payload)
    if not messages:
        print("[Webhook] Payload ignored (unsupported format)")
        return {"status": "ignored"}

    for message in messages:
        await db.persist_message(message)

    primary = messages[0]
    return {
        "status": "ok",
        "msg_id": primary.id,
        "direction": primary.direction,
        "status": primary.status,
        "persisted": len(messages),
    }


def _extract_messages_from_payload(payload: Dict[str, Any]) -> List[Message]:
    messages: List[Message] = []

    if {"direction", "content", "conversation_id"}.issubset(payload.keys()):
        direction = payload.get("direction") or "inbound"
        status = "queued" if direction == "outbound" else "received"
        timestamp = _to_datetime(payload.get("timestamp"))
        messages.append(
            Message(
                id=payload.get("id", 0),
                conversation_id=payload["conversation_id"],
                sender=payload.get("sender", "unknown"),
                content=payload.get("content", ""),
                timestamp=timestamp,
                direction=direction,
                status=status,
            )
        )
        return messages

    event = payload.get("event")
    data = payload.get("data", {}) or {}

    conversation = (
        payload.get("conversation")
        or data.get("conversation")
        or {}
    )
    conversation_id = (
        conversation.get("id")
        or payload.get("conversation_id")
        or data.get("conversation_id")
        or 0
    )

    if event == "conversation_created":
        timestamp = (
            conversation.get("created_at")
            or conversation.get("timestamp")
            or payload.get("created_at")
            or payload.get("timestamp")
        )
        sender_info = (
            conversation.get("meta", {}).get("sender")
            or payload.get("sender")
            or data.get("sender")
        )
        messages.append(
            Message(
                id=0,
                conversation_id=conversation_id,
                sender=_extract_sender(sender_info),
                content="[conversation_created]",
                timestamp=_to_datetime(timestamp),
                direction="inbound",
                status="received",
            )
        )
        return messages

    message_data: Dict[str, Any] = (
        payload.get("message")
        or data.get("message")
        or (
            conversation.get("messages")[-1]
            if isinstance(conversation.get("messages"), list)
            and conversation.get("messages")
            else None
        )
        or payload
    )

    if not isinstance(message_data, dict):
        return messages

    message_event = event or message_data.get("event")
    message_type_raw = (
        message_data.get("message_type")
        or payload.get("message_type")
        or data.get("message_type")
    )
    message_type = _normalize_message_type(message_type_raw, default="incoming")

    if message_event not in {"message_created", "message_updated", None}:
        return messages

    direction = "inbound" if message_type == "incoming" else "outbound"
    status = "received" if direction == "inbound" else "queued"

    sender_info: Union[str, Dict[str, Any], None] = (
        message_data.get("sender")
        or payload.get("sender")
        or data.get("sender")
        or conversation.get("meta", {}).get("sender")
    )
    sender = _extract_sender(sender_info)

    content = (
        message_data.get("content")
        or payload.get("content")
        or data.get("content")
        or ""
    )

    message_id = message_data.get("id") or payload.get("id", 0)
    if conversation_id == 0:
        conversation_id = (
            message_data.get("conversation_id")
            or payload.get("conversation_id")
            or data.get("conversation_id")
            or 0
        )

    created_at = (
        message_data.get("created_at")
        or payload.get("created_at")
        or payload.get("timestamp")
    )

    if conversation_id == 0:
        return messages

    messages.append(
        Message(
            id=message_id or 0,
            conversation_id=conversation_id,
            sender=sender,
            content=content,
            timestamp=_to_datetime(created_at),
            direction=direction,
            status=status,
        )
    )

    return messages


def _extract_sender(sender: Union[str, Dict[str, Any], None]) -> str:
    if isinstance(sender, str):
        return sender
    if isinstance(sender, dict):
        return (
            sender.get("email")
            or sender.get("identifier")
            or sender.get("name")
            or "unknown"
        )
    return "unknown"


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _normalize_message_type(message_type: Any, default: str = "incoming") -> str:
    if isinstance(message_type, str):
        lowered = message_type.lower()
        if lowered in {"incoming", "outgoing"}:
            return lowered
        if lowered == "template":
            return "incoming"
    if isinstance(message_type, int):
        mapping = {
            0: "incoming",  # contact message
            1: "outgoing",  # agent message
            2: "outgoing",  # private notes/system
            3: "incoming",  # templates/system prompts treated as inbound
        }
        return mapping.get(message_type, default)
    return default
