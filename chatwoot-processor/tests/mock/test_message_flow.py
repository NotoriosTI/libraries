import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.dependencies import get_db_adapter
from src.main import app


@pytest.mark.asyncio
async def test_webhook_persists_and_worker_sends() -> None:
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            worker = app.state.outbound_worker
            assert worker is not None

            worker.poll_interval = 0.05
            worker.chatwoot.send_message = AsyncMock(return_value=True)

            timestamp = datetime.now(timezone.utc).isoformat()

            inbound_payload = {
                "id": 0,
                "conversation_id": 1,
                "sender": "contact",
                "content": "Hello there",
                "timestamp": timestamp,
                "direction": "inbound",
                "status": "received",
            }

            inbound_response = await client.post("/webhook/chatwoot", json=inbound_payload)
            assert inbound_response.status_code == 200

            inbound_id = inbound_response.json()["msg_id"]
            db = get_db_adapter()

            inbound_message = await db.get_message(inbound_id)
            assert inbound_message is not None
            assert inbound_message.direction == "inbound"
            assert inbound_message.status == "received"

            outbound_payload = {
                "id": 0,
                "conversation_id": 2,
                "sender": "agent",
                "content": "Hi! How can I help?",
                "timestamp": timestamp,
                "direction": "outbound",
                "status": "queued",
            }

            outbound_response = await client.post("/webhook/chatwoot", json=outbound_payload)
            assert outbound_response.status_code == 200
            outbound_id = outbound_response.json()["msg_id"]

            async def wait_for_status(expected_status: str):
                for _ in range(50):
                    message = await db.get_message(outbound_id)
                    if message and message.status == expected_status:
                        return message
                    await asyncio.sleep(0.1)
                raise AssertionError(
                    f"Timed out waiting for outbound message to reach '{expected_status}'"
                )

            outbound_message = await wait_for_status("sent")
            assert outbound_message.direction == "outbound"
    finally:
        db_adapter = getattr(app.state, "db_adapter", None)
        if db_adapter is not None:
            await db_adapter.engine.dispose(close=True)
        await lifespan.__aexit__(None, None, None)
