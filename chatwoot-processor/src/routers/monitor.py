from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException

from src.db.session import get_async_sessionmaker
from src.models.conversation import Conversation
from src.models.message import Message, MessageRecord

router = APIRouter(tags=["messages"])


@router.get("/messages/count")
async def message_count() -> dict:
    """
    Return the total number of persisted messages.
    """

    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(sa.select(sa.func.count(MessageRecord.id)))
        count = int(result.scalar_one())
    return {"count": count}


@router.get("/messages/latest", response_model=Message)
async def latest_message() -> Message:
    """
    Fetch the most recent message by primary key ordering.
    """

    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            sa.select(MessageRecord, Conversation.user_identifier)
            .join(Conversation, Conversation.id == MessageRecord.conversation_id)
            .order_by(MessageRecord.id.desc())
            .limit(1)
        )
        row = result.first()

    if row is None:
        raise HTTPException(status_code=404, detail="No messages available")

    record, sender = row
    return Message(
        id=record.id,
        conversation_id=record.conversation_id,
        sender=sender,
        content=record.content,
        timestamp=record.timestamp,
        direction=record.direction.value,
        status=record.status.value,
    )
