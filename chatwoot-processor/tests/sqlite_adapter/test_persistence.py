from datetime import datetime, timezone

import pytest

from src.models.message import Message

pytestmark = pytest.mark.asyncio


async def test_persist_and_fetch_pending(db_adapter):
    msg = Message(
        id=1,
        conversation_id=123,
        sender="user@example.com",
        content="Hello!",
        timestamp=datetime.now(timezone.utc),
        direction="outbound",
        status="queued",
    )

    await db_adapter.persist_message(msg)

    results = await db_adapter.fetch_pending()
    assert len(results) == 1
    stored = results[0]
    assert stored.content == "Hello!"
    assert stored.id == msg.id
    assert stored.direction == "outbound"
