from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.session import get_async_engine, get_async_sessionmaker
from src.routers import outbound, webhook

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_alembic(command_name: str, revision: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command_name, revision],
        check=True,
        cwd=PROJECT_ROOT,
    )


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("webhook_flow_db")
    db_path = db_dir / "webhook.sqlite"
    url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["TEST_DATABASE_URL"] = url
    get_async_engine.cache_clear()
    get_async_sessionmaker.cache_clear()
    return url


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(database_url: str) -> Generator[None, None, None]:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
    try:
        yield
    finally:
        _run_alembic("downgrade", "base")


@pytest.fixture(scope="session")
def session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return get_async_sessionmaker()


@pytest_asyncio.fixture
async def fastapi_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()
    app.include_router(webhook.router)
    app.include_router(outbound.router)
    yield app


@pytest_asyncio.fixture
async def async_client(fastapi_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
