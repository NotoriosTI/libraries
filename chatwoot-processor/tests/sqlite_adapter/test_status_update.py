from datetime import datetime, timezone

import pytest

from src.models.message import Message

pytestmark = pytest.mark.asyncio


async def test_update_status(db_adapter):
    msg = Message(
        id=1,
        conversation_id=321,
        sender="agent@example.com",
        content="OK",
        timestamp=datetime.now(timezone.utc),
        direction="outbound",
        status="queued",
    )

    await db_adapter.persist_message(msg)
    await db_adapter.update_status(msg.id, "sent")

    results = await db_adapter.fetch_pending()
    assert len(results) == 0

    stored = await db_adapter.get_message(msg.id)
    assert stored is not None
    assert stored.status == "sent"
