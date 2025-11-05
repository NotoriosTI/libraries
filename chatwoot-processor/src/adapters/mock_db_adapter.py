import asyncio
from typing import List, Optional

from src.interfaces.protocols import MessageReader, MessageWriter
from src.models.message import Message


class MockDBAdapter(MessageReader, MessageWriter):
    """
    Simple in-memory persistence layer used for the mock phase.
    """

    def __init__(self) -> None:
        self.messages: List[Message] = []
        self._id_counter = 1
        self._lock = asyncio.Lock()

    async def init_db(self) -> None:
        # No-op for in-memory adapter
        return None

    async def persist_message(self, msg: Message) -> None:
        async with self._lock:
            if msg.id <= 0:
                msg.id = self._id_counter
                self._id_counter += 1
            else:
                self._id_counter = max(self._id_counter, msg.id + 1)
            self.messages.append(msg)
            print(f"[DB] Persisted message: {msg.model_dump()}")

    async def fetch_queued_outbound(self) -> List[Message]:
        async with self._lock:
            return [
                m
                for m in self.messages
                if m.direction == "outbound" and m.status == "queued"
            ]

    async def fetch_pending(self) -> List[Message]:
        return await self.fetch_queued_outbound()

    async def fetch_unread_inbound(self, provider_id: str) -> List[Message]:
        async with self._lock:
            return [
                m
                for m in self.messages
                if m.direction == "inbound" and m.status == "received"
            ]

    async def update_status(self, msg_id: int, status: str) -> None:
        async with self._lock:
            for message in self.messages:
                if message.id == msg_id:
                    message.status = status
                    print(f"[DB] Updated message {msg_id} -> {status}")
                    return
            print(f"[DB] Message {msg_id} not found for update")

    async def get_message(self, msg_id: int) -> Optional[Message]:
        async with self._lock:
            for message in self.messages:
                if message.id == msg_id:
                    return message
        return None

    async def list_messages(self) -> List[Message]:
        async with self._lock:
            return list(self.messages)
