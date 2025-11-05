from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.dependencies import get_db_adapter
from src.routers import inbound

pytestmark = pytest.mark.asyncio


async def test_webhook_integration(db_adapter):
    app = FastAPI()
    app.include_router(inbound.router)
    app.dependency_overrides[get_db_adapter] = lambda: db_adapter

    payload = {
        "conversation_id": 555,
        "sender": "contact@example.com",
        "content": "Hello from webhook",
        "direction": "inbound",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhook/chatwoot", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["persisted"] == 1

    messages = await db_adapter.list_messages()
    assert len(messages) == 1
    stored = messages[0]
    assert stored.content == payload["content"]
    assert stored.direction == "inbound"
    assert stored.status == "received"
    assert stored.id == data["msg_id"]
