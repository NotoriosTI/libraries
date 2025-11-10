from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from src.db.session import get_async_sessionmaker
from src.services.conversation_service import (
    get_or_open_conversation,
    persist_inbound,
    resolve_sender,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["chatwoot"])


@router.post("/chatwoot")
async def handle_chatwoot_webhook(request: Request) -> dict[str, Any]:
    try:
        payload_raw = await request.json()
    except ValueError as exc:  # pragma: no cover - FastAPI already validated JSON
        logger.warning("Invalid JSON payload received from webhook: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json")

    if not isinstance(payload_raw, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload_must_be_object")

    payload = dict(payload_raw)
    _normalise_payload(payload)

    try:
        user_identifier, channel = resolve_sender(payload)
    except ValueError as exc:
        logger.info("Webhook ignored due to sender resolution failure: %s", exc)
        return {"status": "ignored", "reason": "unresolved_sender"}

    content = _extract_content(payload)
    if not content or not content.strip():
        logger.info("Webhook ignored because content is empty for user=%s", user_identifier)
        return {"status": "ignored", "reason": "empty_content"}

    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        try:
            conversation = await get_or_open_conversation(session, user_identifier, channel)
            message = await persist_inbound(session, conversation, content)
        except ValueError as exc:
            logger.warning("Webhook processing error user=%s: %s", user_identifier, exc)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    logger.debug(
        "Webhook processed conversation_id=%s message_id=%s", conversation.id, message.id
    )
    return {
        "conversation_id": conversation.id,
        "message_id": message.id,
        "direction": message.direction.value,
        "status": message.status.value,
    }


def _normalise_payload(payload: dict[str, Any]) -> None:
    if "channel_type" not in payload:
        inbox = payload.get("inbox")
        if isinstance(inbox, dict) and inbox.get("channel_type"):
            payload["channel_type"] = inbox["channel_type"]

    contact = payload.get("contact")
    if not isinstance(contact, dict):
        sender = payload.get("sender")
        if isinstance(sender, dict):
            payload["contact"] = sender
        elif isinstance(sender, str) and sender.strip():
            payload["contact"] = {"email": sender.strip()}

    contact = payload.get("contact")
    if "channel_type" not in payload and isinstance(contact, dict):
        if contact.get("phone_number"):
            payload["channel_type"] = "whatsapp"
        elif contact.get("email"):
            payload["channel_type"] = "email"

    if "channel_type" not in payload:
        payload["channel_type"] = "email"
        contact = payload.setdefault("contact", {})
        if isinstance(contact, dict) and "email" not in contact:
            contact["email"] = "test@chatwoot.widget"


def _extract_content(payload: dict[str, Any]) -> str:
    direct_content = payload.get("content")
    if isinstance(direct_content, str) and direct_content.strip():
        return direct_content

    message = payload.get("message")
    if isinstance(message, dict):
        message_content = message.get("content")
        if isinstance(message_content, str):
            return message_content

    data = payload.get("data")
    if isinstance(data, dict):
        data_content = data.get("content")
        if isinstance(data_content, str):
            return data_content

    return ""
