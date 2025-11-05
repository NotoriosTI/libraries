from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationChannel
from src.models.message import MessageDirection, MessageRecord, MessageStatus


_ALLOWED_TRANSITIONS: dict[MessageDirection, dict[MessageStatus, set[MessageStatus]]] = {
    MessageDirection.INBOUND: {
        MessageStatus.RECEIVED: {MessageStatus.READ},
    },
    MessageDirection.OUTBOUND: {
        MessageStatus.QUEUED: {MessageStatus.SENT, MessageStatus.FAILED},
    },
}

_CONVERSATION_LOCKS: dict[tuple[str, ConversationChannel], asyncio.Lock] = {}
_LOCK_REGISTRY_MUTEX = asyncio.Lock()


def resolve_sender(payload: dict) -> tuple[str, str]:
    """Resolve sender identity and logical channel from a webhook payload."""

    channel_type = str(payload.get("channel_type", "")).strip().lower()
    contact = payload.get("contact") or {}

    if channel_type == "whatsapp":
        identifier = contact.get("phone_number")
        channel = ConversationChannel.WHATSAPP.value
    elif channel_type == "email":
        identifier = contact.get("email")
        channel = ConversationChannel.EMAIL.value
    elif channel_type == "webwidget":
        identifier = contact.get("email") or "test@chatwoot.widget"
        channel = ConversationChannel.EMAIL.value
    else:
        raise ValueError("Unsupported channel type")

    if not identifier:
        raise ValueError("Missing sender identifier for channel")

    resolved = str(identifier).strip()
    if not resolved:
        raise ValueError("Sender identifier cannot be empty")

    return resolved, channel


async def get_or_open_conversation(
    session: AsyncSession,
    user_identifier: str,
    channel: str | ConversationChannel,
) -> Conversation:
    """Fetch an active conversation or open a new one in a transaction."""

    channel_enum = _coerce_channel(channel)
    attempts = 0

    async with _acquire_conversation_lock(user_identifier, channel_enum):
        while True:
            try:
                async with _ensure_transaction(session):
                    return await _get_or_open_conversation_impl(
                        session, user_identifier, channel_enum
                    )
            except IntegrityError:
                attempts += 1
                if session.in_transaction():
                    await session.rollback()
                if attempts >= 2:
                    raise


async def close_active_conversations(
    session: AsyncSession,
    user_identifier: str,
    channel: str | ConversationChannel,
) -> list[Conversation]:
    """Deactivate any active conversations for the given identifier and channel."""

    channel_enum = _coerce_channel(channel)

    async with _ensure_transaction(session):
        result = await session.execute(
            sa.select(Conversation)
            .where(
                Conversation.user_identifier == user_identifier,
                Conversation.channel == channel_enum,
                Conversation.is_active.is_(True),
            )
            .with_for_update()
        )
        conversations = list(result.scalars())
        if not conversations:
            return []

        ended_at = _utcnow()
        for conversation in conversations:
            conversation.is_active = False
            conversation.ended_at = ended_at

        await session.flush()
        return conversations


async def persist_inbound(
    session: AsyncSession,
    conversation: Conversation,
    content: str,
) -> MessageRecord:
    """Persist an inbound message tied to the provided conversation."""

    if not content or not content.strip():
        raise ValueError("Inbound message content cannot be empty")

    async with _ensure_transaction(session):
        conversation_id = _conversation_identity(conversation)
        conversation_db = await _lock_conversation(session, conversation_id)
        if conversation_db is None:
            raise ValueError("Conversation not found when persisting inbound message")

        message = MessageRecord(
            conversation_id=conversation_db.id,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.RECEIVED,
            content=content,
            timestamp=_utcnow(),
        )
        session.add(message)
        await session.flush()
        return message


async def persist_outbound(
    session: AsyncSession,
    conversation: Conversation,
    content: str,
) -> MessageRecord:
    """Persist an outbound message for an active conversation."""

    if not content or not content.strip():
        raise ValueError("Outbound message content cannot be empty")

    async with _ensure_transaction(session):
        conversation_id = _conversation_identity(conversation)
        conversation_db = await _lock_conversation(session, conversation_id)
        if conversation_db is None:
            raise ValueError("Conversation not found when persisting outbound message")
        if not conversation_db.is_active:
            raise ValueError("Outbound messages require an active conversation")

        message = MessageRecord(
            conversation_id=conversation_db.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.QUEUED,
            content=content,
            timestamp=_utcnow(),
        )
        session.add(message)
        await session.flush()
        return message


async def update_message_status(
    session: AsyncSession, message_id: int, new_status: str | MessageStatus
) -> MessageRecord:
    """Update a message status enforcing allowed transitions."""

    target_status = _coerce_status(new_status)

    async with _ensure_transaction(session):
        result = await session.execute(
            sa.select(MessageRecord)
            .where(MessageRecord.id == message_id)
            .with_for_update()
        )
        message = result.scalar_one_or_none()
        if message is None:
            raise ValueError("Message not found")

        allowed = _ALLOWED_TRANSITIONS.get(message.direction, {}).get(message.status)
        if not allowed or target_status not in allowed:
            raise ValueError(
                f"Invalid status transition from {message.status.value} to {target_status.value}"
            )

        message.status = target_status
        await session.flush()
        return message


async def _get_or_open_conversation_impl(
    session: AsyncSession,
    user_identifier: str,
    channel_enum: ConversationChannel,
) -> Conversation:
    result = await session.execute(
        sa.select(Conversation)
        .where(
            Conversation.user_identifier == user_identifier,
            Conversation.channel == channel_enum,
            Conversation.is_active.is_(True),
        )
        .with_for_update()
    )
    conversation = result.scalars().first()
    if conversation:
        return conversation

    timestamp = _utcnow()

    await session.execute(
        sa.update(Conversation)
        .where(
            Conversation.user_identifier == user_identifier,
            Conversation.channel == channel_enum,
            Conversation.is_active.is_(True),
        )
        .values(is_active=False, ended_at=timestamp)
        .execution_options(synchronize_session=False)
    )

    new_conversation = Conversation(
        user_identifier=user_identifier,
        channel=channel_enum,
        is_active=True,
        started_at=timestamp,
        ended_at=None,
    )
    session.add(new_conversation)
    await session.flush()
    return new_conversation


async def _lock_conversation(
    session: AsyncSession, conversation_id: int
) -> Conversation | None:
    result = await session.execute(
        sa.select(Conversation)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )
    return result.scalars().first()


@asynccontextmanager
async def _ensure_transaction(session: AsyncSession) -> AsyncIterator[None]:
    if session.in_transaction() or session.in_nested_transaction():
        yield
        return

    async with session.begin():
        yield


@asynccontextmanager
async def _acquire_conversation_lock(
    user_identifier: str, channel: ConversationChannel
) -> AsyncIterator[None]:
    async with _LOCK_REGISTRY_MUTEX:
        lock = _CONVERSATION_LOCKS.get((user_identifier, channel))
        if lock is None:
            lock = asyncio.Lock()
            _CONVERSATION_LOCKS[(user_identifier, channel)] = lock

    await lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _coerce_channel(channel: str | ConversationChannel) -> ConversationChannel:
    if isinstance(channel, ConversationChannel):
        return channel

    try:
        return ConversationChannel(channel)
    except ValueError as exc:
        raise ValueError(f"Unknown conversation channel: {channel}") from exc


def _conversation_identity(conversation: Conversation) -> int:
    inspector = sa.inspect(conversation)
    identity = inspector.identity
    if not identity:
        raise ValueError("Conversation must be persisted before writing messages")

    conversation_id = identity[0]
    if conversation_id is None:
        raise ValueError("Conversation primary key is not available")

    return int(conversation_id)


def _coerce_status(status: str | MessageStatus) -> MessageStatus:
    if isinstance(status, MessageStatus):
        return status

    try:
        return MessageStatus(status)
    except ValueError as exc:
        raise ValueError(f"Unknown message status: {status}") from exc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "resolve_sender",
    "get_or_open_conversation",
    "close_active_conversations",
    "persist_inbound",
    "persist_outbound",
    "update_message_status",
]
