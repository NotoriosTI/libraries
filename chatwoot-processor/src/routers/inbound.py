from typing import Union

from fastapi import APIRouter, Depends

from src.adapters.mock_db_adapter import MockDBAdapter
from src.dependencies import get_db_adapter
from src.models.message import Message
from src.models.webhook import ChatwootWebhookPayload

router = APIRouter(tags=["messages"])


@router.post("/webhook/chatwoot")
async def receive_chatwoot_webhook(
    payload: Union[ChatwootWebhookPayload, Message],
    db: MockDBAdapter = Depends(get_db_adapter),
) -> dict:
    """
    Persist incoming Chatwoot webhook payloads or legacy mock messages.
    """

    if isinstance(payload, ChatwootWebhookPayload):
        print(f"[Webhook] Received {payload.event}")

        direction = "inbound" if payload.message_type == "incoming" else "outbound"
        status = "received" if direction == "inbound" else "queued"
        sender = payload.sender.get("email") or payload.sender.get("name") or "unknown"

        message = Message(
            id=payload.id,
            conversation_id=payload.conversation_id,
            sender=sender,
            content=payload.content,
            timestamp=payload.created_at,
            direction=direction,
            status=status,
        )
    else:
        message = payload.model_copy()
        print(f"[Webhook] Received mock message {message.id}")
        if message.direction == "outbound":
            message.status = "queued"
        else:
            message.direction = "inbound"
            message.status = "received"

    direction = message.direction
    status = message.status

    await db.persist_message(message)
    return {"status": "ok", "msg_id": message.id, "direction": direction, "status": status}
