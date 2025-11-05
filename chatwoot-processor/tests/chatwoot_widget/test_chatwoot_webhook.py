from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.db.session import get_async_sessionmaker
from src.main import app
from src.models.conversation import Conversation
from src.models.message import MessageDirection, MessageRecord, MessageStatus
from src.routers import outbound as outbound_router

TEST_DB_PATH = Path("test_chatwoot_webhook.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ.setdefault("CHATWOOT_PROCESSOR_TOKEN", "test-token")
os.environ.setdefault("CHATWOOT_PROCESSOR_ACCOUNT_ID", "12")
os.environ.setdefault("CHATWOOT_PROCESSOR_PORT", "8000")
os.environ.setdefault("CHATWOOT_BASE_URL", "https://app.chatwoot.com")
os.environ.setdefault("CHATWOOT_DATABASE_URL", f"sqlite+aiosqlite:///{TEST_DB_PATH}")


@pytest.mark.asyncio
async def test_chatwoot_webhook_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
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
            assert inbound_body["direction"] == MessageDirection.INBOUND.value
            assert inbound_body["status"] == MessageStatus.RECEIVED.value

            session_factory = get_async_sessionmaker()
            async with session_factory() as session:
                conversation = await session.get(Conversation, inbound_body["conversation_id"])
                assert conversation is not None
                assert conversation.user_identifier == "visitor@example.com"

                inbound_record = await session.get(MessageRecord, inbound_body["message_id"])
                assert inbound_record is not None
                assert inbound_record.status == MessageStatus.RECEIVED
                assert inbound_record.content == inbound_payload["content"]
                assert inbound_record.timestamp.isoformat().startswith(timestamp_iso[:19])

            adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.95)
            monkeypatch.setattr(outbound_router, "get_chatwoot_adapter", lambda env: adapter)

            outbound_response = await client.post(
                "/outbound/send",
                json={
                    "conversation_id": inbound_body["conversation_id"],
                    "content": "Agent reply",
                },
            )
            assert outbound_response.status_code == 200
            outbound_payload = outbound_response.json()["response"]
            assert outbound_payload["status"] == "sent"

            async with session_factory() as session:
                result = await session.execute(
                    select(MessageRecord)
                    .where(
                        MessageRecord.conversation_id == inbound_body["conversation_id"],
                        MessageRecord.direction == MessageDirection.OUTBOUND,
                    )
                    .order_by(MessageRecord.id.desc())
                    .limit(1)
                )
                outbound_record = result.scalars().first()
                assert outbound_record is not None
                assert outbound_record.status == MessageStatus.SENT
                assert outbound_record.content == "Agent reply"
    finally:
        db_adapter = getattr(app.state, "db_adapter", None)
        if db_adapter is not None:
            await db_adapter.engine.dispose(close=True)
        await lifespan.__aexit__(None, None, None)
