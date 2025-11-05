from __future__ import annotations

import pytest

from src.workers.outbound_worker import OutboundWorker

from .utils import build_outbound_message


pytestmark = pytest.mark.asyncio


async def test_synthetic_outbound_cycle(db_adapter, chatwoot_adapter, monkeypatch):
    send_log: list[int] = []

    async def fake_send(msg):  # noqa: D401
        """Pretend to deliver and record the message id."""

        print(f"[Test] Synthetic delivery attempt for msg={msg.id}")  # noqa: T201
        send_log.append(msg.id)
        return True

    monkeypatch.setattr(chatwoot_adapter, "send_message", fake_send)

    message = build_outbound_message(
        msg_id=1,
        conversation_id=111,
        content="Synthetic test message",
    )

    await db_adapter.persist_message(message)
    worker = OutboundWorker(db_adapter, chatwoot_adapter, poll_interval=0)

    print("[Test] Processing queued outbound messages synthetically")  # noqa: T201
    await worker._process_outbound_messages()

    stored = await db_adapter.get_message(message.id)
    assert stored is not None
    assert stored.status == "sent"
    assert send_log == [message.id]

    pending = await db_adapter.fetch_pending()
    assert pending == []
