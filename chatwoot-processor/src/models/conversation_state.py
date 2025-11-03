from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """
    Tracks aggregate properties for a conversation.
    """

    conversation_id: int
    last_message_id: Optional[int] = None
    last_status: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
