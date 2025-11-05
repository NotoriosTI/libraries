from __future__ import annotations

import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.dependencies import get_db_adapter
from src.routers import inbound


pytestmark = pytest.mark.asyncio


async def test_consume_inbound_marks_read(db_adapter, capsys):
    app = FastAPI()
    app.include_router(inbound.router)
    app.dependency_overrides[get_db_adapter] = lambda: db_adapter

    transport = ASGITransport(app=app)

    payloads = [
        {
            "conversation_id": 777,
            "content": "Hello",
            "sender": "user@example.com",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": "inbound",
        },
        {
            "conversation_id": 777,
            "content": "Any updates?",
            "sender": "user@example.com",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": "inbound",
        },
    ]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for payload in payloads:
            response = await client.post("/webhook/chatwoot", json=payload)
            assert response.status_code == 200

    unread = await db_adapter.fetch_unread_inbound("widget")
    print(
        "[Test] Unread before consume -> "
        + ", ".join(f"(id={m.id}, status={m.status})" for m in unread)
    )
    assert len(unread) == 2
    assert all(m.status == "received" for m in unread)

    consumed = await db_adapter.consume_inbound("widget")
    print(
        "[Test] Consumed -> "
        + ", ".join(f"(id={m.id}, status={m.status})" for m in consumed)
    )
    assert len(consumed) == 2
    assert all(m.status == "read" for m in consumed)

    remaining = await db_adapter.fetch_unread_inbound("widget")
    print(f"[Test] Unread after consume -> {remaining}")
    assert remaining == []

    stored = await db_adapter.list_messages()
    assert all(m.status == "read" for m in stored)

    captured = capsys.readouterr().out
    assert "Unread before consume" in captured
    assert "Consumed" in captured
    assert "Unread after consume" in captured

    app.dependency_overrides.clear()
