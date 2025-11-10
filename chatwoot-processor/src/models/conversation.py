from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression, text

from src.db.base import Base
from ._types import PRIMARY_KEY_TYPE

if TYPE_CHECKING:
    from .message import MessageRecord


class ConversationChannel(StrEnum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    WEB = "web"


class Conversation(Base):
    __tablename__ = "conversation"

    __table_args__ = (
        Index(
            "ix_conversation_user_identifier_channel_is_active",
            "user_identifier",
            "channel",
            "is_active",
        ),
        Index(
            "uq_conversation_active_identifier_channel",
            "user_identifier",
            "channel",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(
        PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True
    )
    user_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(
            ConversationChannel,
            name="channel_enum",
            schema=Base.metadata.schema,
            create_type=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=expression.true()
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["MessageRecord"]] = relationship(
        "MessageRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            "Conversation("
            f"id={self.id!r}, user_identifier={self.user_identifier!r}, "
            f"channel={self.channel.value!r}, is_active={self.is_active!r}"
            ")"
        )
