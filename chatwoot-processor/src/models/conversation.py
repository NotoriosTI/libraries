from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Enum, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression, text

from src.db.base import Base
from ._types import PRIMARY_KEY_TYPE

if TYPE_CHECKING:
    from .message import MessageRecord


class ConversationSender(BaseModel):
    """Represents the contact associated with a conversation."""

    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    availability_status: Optional[str] = None
    blocked: Optional[bool] = None
    type: Optional[str] = None
    additional_attributes: Dict[str, Any] = Field(default_factory=dict)
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ConversationMessage(BaseModel):
    """Represents a single Chatwoot message contained in a conversation response."""

    id: int
    conversation_id: int
    content: str
    account_id: int
    inbox_id: int
    message_type: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    private: bool
    status: str
    source_id: Optional[str] = None
    content_type: Optional[str] = None
    processed_message_content: Optional[str] = None
    sender: Optional[ConversationSender] = None
    content_attributes: Dict[str, Any] = Field(default_factory=dict)
    sentiment: Dict[str, Any] = Field(default_factory=dict)
    additional_attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ConversationModel(BaseModel):
    """Pydantic representation of a Chatwoot conversation payload."""

    id: int
    uuid: Optional[str] = None
    account_id: int
    inbox_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    unread_count: int
    additional_attributes: Dict[str, Any] = Field(default_factory=dict)
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    sender: Optional[ConversationSender] = None
    messages: List[ConversationMessage] = Field(default_factory=list)
    last_non_activity_message: Optional[ConversationMessage] = None

    model_config = ConfigDict(extra="allow")


class ConversationList(BaseModel):
    """Envelope returned by the Chatwoot conversations endpoint."""

    meta: Dict[str, Any] = Field(default_factory=dict)
    payload: List[ConversationModel]


class ConversationsResponse(BaseModel):
    """Root response object returned by Chatwoot."""

    data: ConversationList


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
