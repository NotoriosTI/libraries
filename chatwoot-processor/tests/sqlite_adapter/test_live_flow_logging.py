from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool

from src.adapters.sqlite_db_adapter import SQLiteDBAdapter
from src.dependencies import get_db_adapter
from src.models.message import Message
from src.routers import inbound


LIVE_FLOW_ENABLED = os.getenv("CHATWOOT_LIVE_TEST_ENABLED") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE_FLOW_ENABLED,
    reason="SQLite live walkthrough disabled; set CHATWOOT_SQLITE_LIVE_TEST_ENABLED=1",
)


class LoggingSQLiteDBAdapter(SQLiteDBAdapter):
    async def persist_message(self, msg: Message) -> None:
        print(
            f"[DB] persist_message start -> conv={msg.conversation_id} direction={msg.direction} "
            f"status={msg.status} id={msg.id}"
        )
        await super().persist_message(msg)
        print(f"[DB] persist_message done -> stored id={msg.id}")

    async def update_status(self, msg_id: int, status: str) -> None:
        print(f"[DB] update_status -> id={msg_id} new_status={status}")
        await super().update_status(msg_id, status)

    async def fetch_pending(self):
        print("[DB] fetch_pending called")
        results = await super().fetch_pending()
        print(f"[DB] fetch_pending returned {len(results)} rows")
        return results

    async def list_messages(self):
        messages = await super().list_messages()
        print(
            "[DB] list_messages -> "
            + ", ".join(
                f"(id={m.id}, conv={m.conversation_id}, direction={m.direction}, status={m.status})"
                for m in messages
            )
            if messages
            else "[empty]"
        )
        return messages


@pytest.mark.asyncio
async def test_live_message_walkthrough_logs():
    print("\n[Scenario] Starting live message walkthrough against SQLite adapter")
    adapter = LoggingSQLiteDBAdapter(
        "sqlite+aiosqlite:///:memory:",
        engine_kwargs={
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        },
    )
    await adapter.init_db()

    app = FastAPI()
    app.include_router(inbound.router)
    app.dependency_overrides[get_db_adapter] = lambda: adapter

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        conversation_payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 9001,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta": {"sender": {"email": "new.contact@example.com"}},
            },
        }
        print("[Step] Posting conversation_created webhook")
        response = await client.post("/webhook/chatwoot", json=conversation_payload)
        assert response.status_code == 200

        await adapter.list_messages()

        inbound_payload = {
            "conversation_id": 9001,
            "content": "Hello from the new conversation!",
            "sender": "new.contact@example.com",
            "direction": "inbound",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print("[Step] Posting inbound message webhook")
        response = await client.post("/webhook/chatwoot", json=inbound_payload)
        assert response.status_code == 200
        data = response.json()
        print(f"[Webhook] Response payload -> {data}")

        messages = await adapter.list_messages()
        assert len(messages) == 2

        pending = await adapter.fetch_pending()
        assert pending == []  # inbound messages remain received

        stored = await adapter.get_message(data["msg_id"])
        assert stored is not None
        print(
            f"[Result] Latest message -> id={stored.id}, direction={stored.direction}, status={stored.status}, "
            f"content={stored.content}"
        )

    await adapter.engine.dispose()
    app.dependency_overrides.clear()
