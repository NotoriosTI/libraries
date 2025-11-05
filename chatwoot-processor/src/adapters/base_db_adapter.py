from __future__ import annotations

from typing import List, Optional, Protocol

from src.models.message import Message


class BaseDBAdapter(Protocol):
    async def init_db(self) -> None:
        ...

    async def persist_message(self, msg: Message) -> None:
        ...

    async def fetch_pending(self) -> List[Message]:
        ...

    async def fetch_queued_outbound(self) -> List[Message]:
        ...

    async def fetch_unread_inbound(self, provider_id: str) -> List[Message]:
        ...

    async def update_status(self, msg_id: int, status: str) -> None:
        ...

    async def get_message(self, msg_id: int) -> Optional[Message]:
        ...

    async def list_messages(self) -> List[Message]:
        ...
