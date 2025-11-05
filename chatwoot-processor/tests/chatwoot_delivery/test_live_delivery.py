from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from env_manager import get_config
from src.adapters.sqlite_db_adapter import SQLiteDBAdapter
from src.workers.outbound_worker import OutboundWorker

from .utils import build_outbound_message


pytestmark = pytest.mark.asyncio

LIVE_TEST_ENABLED = bool(get_config("CHATWOOT_LIVE_TEST_ENABLED"))
TIMEOUT_SECONDS = int(get_config("CHATWOOT_LIVE_TEST_TIMEOUT"))
POLL_INTERVAL = float(get_config("CHATWOOT_LIVE_TEST_POLL"))
SQLITE_PATH = Path(get_config("CHATWOOT_SQLITE_DB_PATH"))


@pytest.mark.skipif(
    not LIVE_TEST_ENABLED,
    reason="Live outbound test disabled; set CHATWOOT_LIVE_TEST_ENABLED=1",
)
async def test_live_outbound_delivery(chatwoot_adapter):
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
        existing = await adapter.list_messages()
        baseline_id = max((msg.id for msg in existing), default=0)

        print(
            "[LiveTest] Awaiting new conversation. Open your Chatwoot widget and start a fresh conversation now."
        )  # noqa: T201
        inbound_message = await _wait_for_new_conversation(adapter, baseline_id)
        conversation_id = inbound_message.conversation_id
        print(  # noqa: T201
            f"[LiveTest] Detected conversation_created event id={inbound_message.id} conv={conversation_id}"
        )

        outbound_message = build_outbound_message(
            msg_id=0,
            conversation_id=conversation_id,
            content="[LIVE TEST] Outbound verification",
        )
        await adapter.persist_message(outbound_message)

        worker = OutboundWorker(adapter, chatwoot_adapter, poll_interval=0)
        print(  # noqa: T201
            f"[LiveTest] Dispatching message {outbound_message.id} to conversation {conversation_id}"
        )
        await worker._process_outbound_messages()

        stored = await adapter.get_message(outbound_message.id)
        assert stored is not None, "Outbound message missing after dispatch"
        print(f"[LiveTest] Delivery status -> {stored.status}")  # noqa: T201
        if stored.status != "sent":
            status_code = getattr(chatwoot_adapter, "last_response_status", None)
            response_body = getattr(chatwoot_adapter, "last_response_body", "")
            if status_code == 401:
                pytest.skip(
                    "Chatwoot API returned 401 (invalid access token). Provide a valid CHATWOOT_API_KEY to run the live delivery test."
                )
            if status_code is None and isinstance(response_body, str) and (
                "nodename nor servname" in response_body
                or "Name or service not known" in response_body
            ):
                pytest.skip(
                    "Chatwoot host unreachable (DNS resolution failed). Ensure network access or retry when connection stabilises."
                )
            pytest.fail(
                f"Outbound delivery did not succeed (status={stored.status}, "
                f"api_status={status_code}, api_body={response_body})."
            )

        pending = await adapter.fetch_pending()
        assert all(m.id != outbound_message.id for m in pending)
    finally:
        await adapter.engine.dispose()


async def _wait_for_new_conversation(adapter: SQLiteDBAdapter, baseline_id: int):
    """Wait for the first inbound message in a new conversation and return it."""

    deadline = time.monotonic() + TIMEOUT_SECONDS
    logged_zero_conv = False

    while time.monotonic() < deadline:
        messages = await adapter.list_messages()
        for msg in sorted(messages, key=lambda m: m.id):
            if msg.id <= baseline_id or msg.direction != "inbound":
                continue

            if msg.content == "[conversation_created]" and not logged_zero_conv:
                print(  # noqa: T201
                    "[LiveTest] Conversation created event detected; send a message in the widget to continue."
                )
                logged_zero_conv = True
                continue

            if msg.conversation_id > 0 and msg.status in {"received", "queued", "sent"}:
                return msg

        await asyncio.sleep(POLL_INTERVAL)

    raise AssertionError(
        "Timed out waiting for a new conversation message. After opening the widget, send a chat message to create an inbound event with a valid conversation ID."
    )
