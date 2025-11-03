import os

os.environ.setdefault("CHATWOOT_PROCESSOR_TOKEN", "test-token")
os.environ.setdefault("CHATWOOT_PROCESSOR_ACCOUNT_ID", "12")
os.environ.setdefault("CHATWOOT_PROCESSOR_PORT", "8000")
os.environ.setdefault("CHATWOOT_BASE_URL", "https://app.chatwoot.com")

import asyncio
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from src.dependencies import get_db_adapter
from src.main import app


def test_chatwoot_webhook_integration() -> None:
    asyncio.run(_run_chatwoot_flow())


async def _run_chatwoot_flow() -> None:
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            worker = app.state.outbound_worker
            assert worker is not None

            worker.poll_interval = 0.05
            worker.chatwoot.failure_rate = 0.0

            timestamp = datetime.now(timezone.utc)
            timestamp_iso = timestamp.isoformat()

            inbound_payload = {
                "event": "message_created",
                "id": 501,
                "account_id": 12,
                "conversation_id": 1001,
                "message_type": "incoming",
                "content": "Customer question",
                "sender": {"name": "Visitor", "email": "visitor@example.com"},
                "created_at": timestamp_iso,
            }

            inbound_response = await client.post("/webhook/chatwoot", json=inbound_payload)
            assert inbound_response.status_code == 200
            inbound_body = inbound_response.json()
            assert inbound_body["direction"] == "inbound"
            assert inbound_body["status"] == "received"

            db = get_db_adapter()
            inbound_message = await db.get_message(inbound_payload["id"])
            assert inbound_message is not None
            assert inbound_message.direction == "inbound"
            assert inbound_message.status == "received"
            assert inbound_message.sender == "visitor@example.com"
            assert inbound_message.content == inbound_payload["content"]
            assert inbound_message.conversation_id == inbound_payload["conversation_id"]
            assert inbound_message.timestamp.isoformat() == timestamp_iso

            outbound_payload = {
                "event": "message_created",
                "id": 502,
                "account_id": 12,
                "conversation_id": 2002,
                "message_type": "outgoing",
                "content": "Agent reply",
                "sender": {"name": "Agent Smith"},
                "created_at": timestamp_iso,
            }

            outbound_response = await client.post("/webhook/chatwoot", json=outbound_payload)
            assert outbound_response.status_code == 200
            outbound_body = outbound_response.json()
            assert outbound_body["direction"] == "outbound"
            assert outbound_body["status"] == "queued"

            async def wait_for_status(msg_id: int, expected: str):
                for _ in range(50):
                    message = await db.get_message(msg_id)
                    if message and message.status == expected:
                        return message
                    await asyncio.sleep(0.1)
                raise AssertionError(
                    f"Timed out waiting for message {msg_id} to reach status '{expected}'"
                )

            outbound_message = await wait_for_status(outbound_payload["id"], "sent")
            assert outbound_message.direction == "outbound"
            assert outbound_message.sender == "Agent Smith"
            assert outbound_message.content == outbound_payload["content"]
    finally:
        await lifespan.__aexit__(None, None, None)
