from __future__ import annotations

import asyncio
from datetime import timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.conversation import Conversation, ConversationChannel
from src.models.message import MessageRecord, MessageStatus
from src.services.conversation_service import (
    close_active_conversations,
    get_or_open_conversation,
    persist_inbound,
    persist_outbound,
    resolve_sender,
    update_message_status,
)


def test_resolve_sender_variants() -> None:
    whatsapp_payload = {
        "channel_type": "whatsapp",
        "contact": {"phone_number": "+549112233"},
    }
    email_payload = {
        "channel_type": "email",
        "contact": {"email": "user@example.com"},
    }
    web_payload = {
        "channel_type": "webwidget",
        "contact": {},
    }

    assert resolve_sender(whatsapp_payload) == ("+549112233", "whatsapp")
    assert resolve_sender(email_payload) == ("user@example.com", "email")
    assert resolve_sender(web_payload) == ("test@chatwoot.widget", "email")


def test_resolve_sender_missing_identifier() -> None:
    payload = {"channel_type": "whatsapp", "contact": {}}
    with pytest.raises(ValueError):
        resolve_sender(payload)


def test_resolve_sender_unknown_channel() -> None:
    payload = {"channel_type": "sms", "contact": {"phone_number": "+1"}}
    with pytest.raises(ValueError):
        resolve_sender(payload)


@pytest.mark.asyncio
async def test_get_or_open_conversation_idempotent(db_session: AsyncSession) -> None:
    identifier = "user-idempotent"
    conv_one = await get_or_open_conversation(db_session, identifier, "email")
    conv_two = await get_or_open_conversation(
        db_session, identifier, ConversationChannel.EMAIL
    )

    assert conv_one.id == conv_two.id
    assert conv_one.is_active


@pytest.mark.asyncio
async def test_close_active_opens_new_conversation(db_session: AsyncSession) -> None:
    identifier = "user-switch"
    channel = ConversationChannel.WHATSAPP

    original = await get_or_open_conversation(db_session, identifier, channel)
    closed = await close_active_conversations(db_session, identifier, channel)

    assert len(closed) == 1
    assert not closed[0].is_active
    assert closed[0].ended_at is not None

    successor = await get_or_open_conversation(db_session, identifier, channel)
    assert successor.id != original.id
    assert successor.is_active


@pytest.mark.asyncio
async def test_persist_outbound_requires_active(db_session: AsyncSession) -> None:
    identifier = "user-outbound-guard"
    channel = ConversationChannel.EMAIL

    conversation = await get_or_open_conversation(db_session, identifier, channel)
    await close_active_conversations(db_session, identifier, channel)

    with pytest.raises(ValueError):
        await persist_outbound(db_session, conversation, "should fail")


@pytest.mark.asyncio
async def test_message_status_transitions(db_session: AsyncSession) -> None:
    identifier = "user-status"
    conversation = await get_or_open_conversation(
        db_session, identifier, ConversationChannel.EMAIL
    )

    inbound = await persist_inbound(db_session, conversation, "incoming")
    inbound_id = inbound.id
    updated_inbound = await update_message_status(
        db_session, inbound_id, MessageStatus.READ
    )
    assert updated_inbound.status is MessageStatus.READ

    with pytest.raises(ValueError):
        await update_message_status(db_session, inbound_id, MessageStatus.SENT)

    outbound = await persist_outbound(db_session, conversation, "outgoing")
    outbound_id = outbound.id
    sent_outbound = await update_message_status(db_session, outbound_id, "sent")
    assert sent_outbound.status is MessageStatus.SENT

    with pytest.raises(ValueError):
        await update_message_status(db_session, outbound_id, "read")

    with pytest.raises(ValueError):
        await update_message_status(db_session, outbound_id, "delivered")


@pytest.mark.asyncio
async def test_concurrent_inbounds_use_single_conversation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    identifier = "user-concurrent"

    async def producer(content: str) -> tuple[int, int]:
        async with session_factory() as session:
            conversation = await get_or_open_conversation(
                session, identifier, ConversationChannel.WHATSAPP
            )
            message = await persist_inbound(session, conversation, content)
            return conversation.id, message.id

    results = await asyncio.gather(
        *(producer(f"payload-{idx}") for idx in range(5))
    )

    conversation_ids = {conversation_id for conversation_id, _ in results}
    assert len(conversation_ids) == 1

    async with session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.user_identifier == identifier,
                Conversation.channel == ConversationChannel.WHATSAPP,
                Conversation.is_active.is_(True),
            )
        )
        assert active_count == 1

        message_count = await session.scalar(
            select(func.count())
            .select_from(MessageRecord)
            .where(MessageRecord.conversation_id == next(iter(conversation_ids)))
        )
        assert message_count == 5


@pytest.mark.asyncio
async def test_message_timestamps_are_utc_and_ordered(db_session: AsyncSession) -> None:
    identifier = "user-timestamps"
    conversation = await get_or_open_conversation(
        db_session, identifier, ConversationChannel.EMAIL
    )

    inbound = await persist_inbound(db_session, conversation, "earlier")
    outbound = await persist_outbound(db_session, conversation, "later")

    assert inbound.timestamp.tzinfo == timezone.utc
    assert outbound.timestamp.tzinfo == timezone.utc
    assert inbound.timestamp <= outbound.timestamp


@pytest.mark.asyncio
async def test_cascade_delete_via_service(db_session: AsyncSession) -> None:
    identifier = "user-cascade"
    conversation = await get_or_open_conversation(
        db_session, identifier, ConversationChannel.EMAIL
    )
    await persist_inbound(db_session, conversation, "hello there")
    conversation_id = conversation.id

    async with db_session.begin():
        await db_session.delete(conversation)

    remaining = await db_session.scalar(
        select(func.count())
        .select_from(MessageRecord)
        .where(MessageRecord.conversation_id == conversation_id)
    )
    assert remaining == 0
