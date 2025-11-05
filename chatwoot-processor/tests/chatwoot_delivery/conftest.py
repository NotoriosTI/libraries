from __future__ import annotations

import pytest_asyncio
from sqlalchemy.pool import StaticPool

from src.adapters.chatwoot_rest_adapter import ChatwootRESTAdapter
from src.adapters.sqlite_db_adapter import SQLiteDBAdapter


@pytest_asyncio.fixture
async def db_adapter():
    adapter = SQLiteDBAdapter(
        "sqlite+aiosqlite:///:memory:",
        engine_kwargs={
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        },
    )
    await adapter.init_db()
    try:
        yield adapter
    finally:
        await adapter.engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def chatwoot_adapter():
    # No network calls during fixture creation; tests may monkeypatch send_message.
    yield ChatwootRESTAdapter()
