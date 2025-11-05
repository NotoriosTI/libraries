from __future__ import annotations

from datetime import datetime, timezone

from src.models.message import Message


def build_outbound_message(
    *,
    msg_id: int,
    conversation_id: int,
    content: str,
    status: str = "queued",
) -> Message:
    """Helper to build a queued outbound message with a UTC timestamp."""

    return Message(
        id=msg_id,
        conversation_id=conversation_id,
        sender="synthetic@test",
        content=content,
        timestamp=datetime.now(timezone.utc),
        direction="outbound",
        status=status,
    )
