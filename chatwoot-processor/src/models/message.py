from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from src.db.base import Base
from ._types import PRIMARY_KEY_TYPE

if TYPE_CHECKING:
    from .conversation import Conversation


class Message(BaseModel):
    """
    Represents a message exchanged through Chatwoot.
    """

    id: int = 0
    conversation_id: int
    sender: str
    content: str
    timestamp: datetime
    direction: Literal["inbound", "outbound"]
    status: Literal["received", "queued", "sent", "failed", "read"]


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(StrEnum):
    RECEIVED = "received"
    READ = "read"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class MessageRecord(Base):
    __tablename__ = "message"

    __table_args__ = (
        Index(
            "ix_message_conversation_id_timestamp",
            "conversation_id",
            "timestamp",
        ),
        Index(
            "ix_message_status_direction",
            "status",
            "direction",
        ),
    )

    id: Mapped[int] = mapped_column(
        PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[int] = mapped_column(
        PRIMARY_KEY_TYPE,
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(
            MessageDirection,
            name="direction_enum",
            schema=Base.metadata.schema,
            create_type=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(
            MessageStatus,
            name="status_enum",
            schema=Base.metadata.schema,
            create_type=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            "MessageRecord("
            f"id={self.id!r}, conversation_id={self.conversation_id!r}, "
            f"direction={self.direction.value!r}, status={self.status.value!r}"
            ")"
        )


__all__ = [
    "Message",
    "MessageDirection",
    "MessageRecord",
    "MessageStatus",
]
