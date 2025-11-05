from __future__ import annotations

import os
from datetime import timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.adapters.base_db_adapter import BaseDBAdapter
from src.models.db_message import Base, DBMessage, Direction, Status
from src.models.message import Message


class SQLiteDBAdapter(BaseDBAdapter):
    """
    Asynchronous SQLite-backed persistence layer for Chatwoot messages.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        engine_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        resolved_url = db_url or os.getenv(
            "CHATWOOT_DATABASE_URL", "sqlite+aiosqlite:///./chatwoot_messages.db"
        )
        kwargs: Dict[str, Any] = {"echo": False, "future": True}
        if engine_kwargs:
            kwargs.update(engine_kwargs)
        self.engine = create_async_engine(resolved_url, **kwargs)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def persist_message(self, msg: Message) -> None:
        async with self._sessionmaker() as session:
            if msg.id > 0:
                existing = await session.get(DBMessage, msg.id)
                if existing:
                    existing.conversation_id = msg.conversation_id
                    existing.sender = msg.sender
                    existing.content = msg.content
                    existing.timestamp = msg.timestamp
                    existing.direction = Direction(msg.direction)
                    existing.status = Status(msg.status)
                    await session.commit()
                    return

            db_msg = self._to_db_message(msg)
            session.add(db_msg)
            await session.flush()
            if msg.id <= 0:
                msg.id = db_msg.id
            await session.commit()

    async def fetch_pending(self) -> List[Message]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(DBMessage).where(DBMessage.status == Status.queued)
            )
            db_rows = result.scalars().all()
            return [self._to_message(row) for row in db_rows]

    async def fetch_queued_outbound(self) -> List[Message]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(DBMessage).where(
                    (DBMessage.status == Status.queued)
                    & (DBMessage.direction == Direction.outbound)
                )
            )
            db_rows = result.scalars().all()
            return [self._to_message(row) for row in db_rows]

    async def fetch_unread_inbound(self, provider_id: str) -> List[Message]:
        # provider_id is kept for interface compatibility; it is currently unused.
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(DBMessage).where(
                    (DBMessage.status == Status.received)
                    & (DBMessage.direction == Direction.inbound)
                )
            )
            db_rows = result.scalars().all()
            return [self._to_message(row) for row in db_rows]

    async def consume_inbound(self, provider_id: str) -> List[Message]:
        consumed: list[Message] = []
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(DBMessage).where(
                    (DBMessage.status == Status.received)
                    & (DBMessage.direction == Direction.inbound)
                )
            )
            db_rows = result.scalars().all()
            for row in db_rows:
                row.status = Status.read
                consumed.append(self._to_message(row))
            await session.commit()
        return consumed

    async def update_status(self, msg_id: int, status: str) -> None:
        new_status = Status(status)
        async with self._sessionmaker() as session:
            await session.execute(
                update(DBMessage).where(DBMessage.id == msg_id).values(status=new_status)
            )
            await session.commit()

    async def get_message(self, msg_id: int) -> Optional[Message]:
        async with self._sessionmaker() as session:
            db_msg = await session.get(DBMessage, msg_id)
            return self._to_message(db_msg) if db_msg else None

    async def list_messages(self) -> List[Message]:
        async with self._sessionmaker() as session:
            result = await session.execute(select(DBMessage))
            db_rows = result.scalars().all()
            return [self._to_message(row) for row in db_rows]

    def _to_db_message(self, msg: Message) -> DBMessage:
        status = Status(msg.status)
        direction = Direction(msg.direction)
        db_msg = DBMessage(
            id=msg.id if msg.id > 0 else None,
            conversation_id=msg.conversation_id,
            sender=msg.sender,
            content=msg.content,
            timestamp=msg.timestamp,
            direction=direction,
            status=status,
        )
        return db_msg

    @staticmethod
    def _to_message(db_msg: DBMessage) -> Message:
        timestamp = db_msg.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return Message(
            id=db_msg.id,
            conversation_id=db_msg.conversation_id,
            sender=db_msg.sender,
            content=db_msg.content,
            timestamp=timestamp,
            direction=db_msg.direction.value,
            status=db_msg.status.value,
        )
