from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
