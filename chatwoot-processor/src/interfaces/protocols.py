from datetime import datetime
from typing import List, Protocol, runtime_checkable

from src.models.message import Message


class MessageReader(Protocol):
    async def fetch_queued_outbound(self) -> List[Message]:
        ...

    async def fetch_unread_inbound(self, provider_id: str) -> List[Message]:
        ...

    async def consume_inbound(self, provider_id: str) -> List[Message]:
        ...

    async def fetch_pending(self) -> List[Message]:
        ...


class MessageWriter(Protocol):
    async def persist_message(self, msg: Message) -> None:
        ...

    async def update_status(self, msg_id: int, status: str) -> None:
        ...


class MessageDeliveryClient(Protocol):
    async def send_message(self, msg: Message) -> bool:
        ...


@runtime_checkable
class ChatwootAdapter(Protocol):
    async def send_message(self, conversation_id: int, content: str) -> dict:
        ...

    async def fetch_incoming_messages(
        self, since: datetime | None = None
    ) -> list[dict]:
        ...


__all__ = [
    "MessageReader",
    "MessageWriter",
    "MessageDeliveryClient",
    "ChatwootAdapter",
]
