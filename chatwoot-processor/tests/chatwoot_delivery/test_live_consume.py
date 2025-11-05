import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from env_manager import get_config
from src.adapters.sqlite_db_adapter import SQLiteDBAdapter

LIVE_TEST_ENABLED = bool(get_config("CHATWOOT_LIVE_TEST_ENABLED"))
TIMEOUT_SECONDS = int(get_config("CHATWOOT_LIVE_TEST_TIMEOUT"))
POLL_INTERVAL = float(get_config("CHATWOOT_LIVE_TEST_POLL"))
SQLITE_PATH = Path(get_config("CHATWOOT_SQLITE_DB_PATH"))


@pytest.mark.skipif(
    not LIVE_TEST_ENABLED,
    reason="Live inbound test disabled; set CHATWOOT_LIVE_TEST_ENABLED=1",
)
def test_live_inbound_consume_marks_read():
    asyncio.run(_run_live_consume())


async def _run_live_consume():
    if not SQLITE_PATH.exists():
        pytest.skip(
            f"SQLite database not found at '{SQLITE_PATH}'. Ensure the processor is running before starting the test."
        )

    adapter = SQLiteDBAdapter(
        f"sqlite+aiosqlite:///{SQLITE_PATH}",
        engine_kwargs={"connect_args": {"check_same_thread": False}},
    )
    await adapter.init_db()

    try:
        baseline_id = max((msg.id for msg in await adapter.list_messages()), default=0)
        print("[LiveConsume] Awaiting inbound message; trigger the widget now.")  # noqa: T201
        inbound = await _wait_for_inbound(adapter, baseline_id)
        print(  # noqa: T201
            f"[LiveConsume] Detected inbound message id={inbound.id} conv={inbound.conversation_id} status={inbound.status}"
        )

        unread_before = await adapter.fetch_unread_inbound("widget")
        print(  # noqa: T201
            "[LiveConsume] Unread before consume -> "
            + ", ".join(f"(id={m.id}, status={m.status})" for m in unread_before)
        )

        consumed = await adapter.consume_inbound("widget")
        print(  # noqa: T201
            f"[LiveConsume] Consumed ids -> {[msg.id for msg in consumed]} statuses -> {[msg.status for msg in consumed]}"
        )
        assert any(msg.id == inbound.id and msg.status == "read" for msg in consumed)

        remaining = await adapter.fetch_unread_inbound("widget")
        print(f"[LiveConsume] Remaining unread -> {remaining}")  # noqa: T201
        assert all(msg.status != "received" for msg in remaining)
    finally:
        await adapter.engine.dispose()


async def _wait_for_inbound(adapter: SQLiteDBAdapter, baseline_id: int):
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        messages = await adapter.list_messages()
        for message in messages:
            if (
                message.id > baseline_id
                and message.direction == "inbound"
                and message.timestamp and message.timestamp > datetime.fromtimestamp(0, tz=timezone.utc)
            ):
                return message
        await asyncio.sleep(POLL_INTERVAL)
    raise AssertionError("Timed out waiting for inbound message. Send a message via the widget.")
