from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.session import get_async_engine, get_async_sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_alembic(command_name: str, revision: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command_name, revision],
        check=True,
        cwd=PROJECT_ROOT,
    )


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("phase2_conversation_logic_db")
    db_path = db_dir / "logic.sqlite"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["TEST_DATABASE_URL"] = database_url
    get_async_engine.cache_clear()
    get_async_sessionmaker.cache_clear()
    return database_url


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(database_url: str) -> Generator[None, None, None]:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
    yield
    _run_alembic("downgrade", "base")


@pytest.fixture(scope="session")
def session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return get_async_sessionmaker()


@pytest_asyncio.fixture
async def db_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
