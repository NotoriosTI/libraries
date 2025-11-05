from __future__ import annotations

import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .base import SCHEMA_NAME


DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./chatwoot_processor.db"


def get_database_url() -> str:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        return test_url

    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    return DEFAULT_SQLITE_URL


def _schema_translate_map(url: str) -> dict[str, str | None] | None:
    if url.startswith("sqlite"):
        return {SCHEMA_NAME: None}
    return None


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    url = get_database_url()
    execution_options: dict[str, object] = {}
    schema_translate = _schema_translate_map(url)
    if schema_translate:
        execution_options["schema_translate_map"] = schema_translate

    engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        execution_options=execution_options,
    )

    if url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)

    return engine


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, connection_record) -> None:  # type: ignore[override]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@lru_cache(maxsize=1)
def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        yield session
