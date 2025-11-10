from datetime import datetime
from typing import Dict, Literal

from pydantic import BaseModel


class ChatwootWebhookPayload(BaseModel):
    event: str
    id: int
    account_id: int
    conversation_id: int
    message_type: Literal["incoming", "outgoing"]
    content: str
    sender: Dict[str, str]
    created_at: datetime
