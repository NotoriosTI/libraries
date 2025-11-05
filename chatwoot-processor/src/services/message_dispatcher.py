from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.protocols import ChatwootAdapter
from src.models.conversation import Conversation
from src.models.message import MessageStatus
from src.services.conversation_service import persist_outbound, update_message_status

logger = logging.getLogger(__name__)


async def dispatch_outbound_message(
    session: AsyncSession,
    adapter: ChatwootAdapter,
    conversation: Conversation,
    content: str,
) -> dict:
    """Create outbound message, send via adapter, and update status."""

    async with session.begin():
        message = await persist_outbound(session, conversation, content)

    try:
        response = await adapter.send_message(conversation.id, content)
    except Exception:
        logger.exception(
            "Failed to dispatch outbound message conversation_id=%s",
            conversation.id,
        )
        await _transition_message(session, message.id, MessageStatus.FAILED)
        raise

    await _transition_message(session, message.id, MessageStatus.SENT)
    return response


async def _transition_message(
    session: AsyncSession, message_id: int, status: MessageStatus
) -> None:
    async with session.begin():
        await update_message_status(session, message_id, status)


__all__ = ["dispatch_outbound_message"]
