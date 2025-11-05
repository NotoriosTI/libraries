from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.db.base import Base, SCHEMA_NAME
from src.db.session import get_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _schema_translate_map(url: str) -> dict[str, str | None] | None:
    if url.startswith("sqlite"):
        return {SCHEMA_NAME: None}
    return None


def _version_table_schema(schema_translate_map: dict[str, str | None] | None) -> str | None:
    if schema_translate_map and schema_translate_map.get(SCHEMA_NAME) is None:
        return None
    return SCHEMA_NAME


def get_url() -> str:
    return get_database_url()


def run_migrations_offline() -> None:
    url = get_url()
    schema_translate_map = _schema_translate_map(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=_version_table_schema(schema_translate_map),
        render_as_batch=url.startswith("sqlite"),
        schema_translate_map=schema_translate_map,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = get_url()
    schema_translate_map = _schema_translate_map(url)

    connectable: AsyncEngine = create_async_engine(
        url,
        poolclass=pool.NullPool,
        execution_options={"schema_translate_map": schema_translate_map}
        if schema_translate_map
        else {},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            configure_connection,
            schema_translate_map=schema_translate_map,
        )
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def configure_connection(connection: Connection, **kwargs: Any) -> None:
    schema_translate_map = kwargs.get("schema_translate_map")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=_version_table_schema(schema_translate_map),
        render_as_batch=connection.dialect.name == "sqlite",
        schema_translate_map=schema_translate_map,
    )


def do_run_migrations(connection: Connection) -> None:
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online_sync() -> None:
    asyncio.run(run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online_sync()
