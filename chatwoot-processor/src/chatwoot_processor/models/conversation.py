from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


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


class Direction(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


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

    @computed_field
    @property
    def direction(self) -> Direction:
        """Derive a simple inbound/outbound tag from Chatwoot's message_type field."""

        return Direction.outbound if self.message_type else Direction.inbound


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
