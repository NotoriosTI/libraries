import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.asyncio


async def test_db_initialization(db_adapter):
    async with db_adapter.engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert "messages" in tables
