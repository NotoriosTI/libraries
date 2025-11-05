from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator, Generator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_engine, get_async_sessionmaker
from src.models.conversation import Conversation, ConversationChannel
from src.models.message import MessageDirection, MessageRecord, MessageStatus

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_alembic(command_name: str, revision: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command_name, revision],
        check=True,
        cwd=PROJECT_ROOT,
    )


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("phase2_1_db")
    db_path = db_dir / "communication.sqlite"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["TEST_DATABASE_URL"] = database_url
    return database_url


@pytest.fixture(scope="module", autouse=True)
def apply_migrations(database_url: str) -> Generator[None, None, None]:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
    yield
    _run_alembic("downgrade", "base")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_tables_exist() -> None:
    engine = get_async_engine()

    async with engine.begin() as conn:
        def _check_tables(sync_conn: sa.Connection) -> None:
            inspector = sa.inspect(sync_conn)
            tables = set(inspector.get_table_names())
            assert "conversation" in tables
            assert "message" in tables

        await conn.run_sync(_check_tables)


@pytest.mark.asyncio
async def test_unique_active_constraint(db_session) -> None:
    conversation_one = Conversation(
        user_identifier="unique-user",
        channel=ConversationChannel.EMAIL,
    )
    db_session.add(conversation_one)
    await db_session.flush()

    conversation_two = Conversation(
        user_identifier="unique-user",
        channel=ConversationChannel.EMAIL,
    )
    db_session.add(conversation_two)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_removes_messages(db_session) -> None:
    conversation = Conversation(
        user_identifier="cascade-user",
        channel=ConversationChannel.WHATSAPP,
    )
    db_session.add(conversation)
    await db_session.flush()

    message = MessageRecord(
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND,
        status=MessageStatus.RECEIVED,
        content="hello world",
    )
    db_session.add(message)
    await db_session.commit()

    await db_session.refresh(conversation)
    await db_session.delete(conversation)
    await db_session.commit()

    remaining = await db_session.scalar(select(func.count()).select_from(MessageRecord))
    assert remaining == 0


@pytest.mark.asyncio
async def test_invalid_enum_rejected(db_session) -> None:
    conversation = Conversation(
        user_identifier="enum-user",
        channel=ConversationChannel.WEB,
    )
    db_session.add(conversation)
    await db_session.flush()

    invalid = MessageRecord(
        conversation_id=conversation.id,
        direction="sideways",  # type: ignore[arg-type]
        status=MessageStatus.RECEIVED,
        content="bad enum",
    )
    db_session.add(invalid)

    with pytest.raises(StatementError):
        await db_session.flush()

    await db_session.rollback()


def test_migrations_idempotent(database_url: str) -> None:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
