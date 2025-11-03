import asyncio
import os
import time

import httpx
import pytest
from rich.console import Console
from rich.tree import Tree

from src.models.message import Message

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
BASE_URL = os.getenv("CHATWOOT_PROCESSOR_BASE_URL", DEFAULT_BASE_URL)
TIMEOUT_SECONDS = int(os.getenv("CHATWOOT_LIVE_TEST_TIMEOUT", "60"))
POLL_INTERVAL = float(os.getenv("CHATWOOT_LIVE_TEST_POLL", "2"))
LIVE_TEST_ENABLED = os.getenv("CHATWOOT_LIVE_TEST_ENABLED") == "1"

console = Console()

pytestmark = pytest.mark.skipif(
    not LIVE_TEST_ENABLED, reason="Live webhook test disabled; set CHATWOOT_LIVE_TEST_ENABLED=1"
)


def test_live_chatwoot_webhook_processed() -> None:
    asyncio.run(_verify_live_webhook())


async def _verify_live_webhook() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        try:
            health = await client.get("/health")
        except httpx.TransportError as exc:  # pragma: no cover - network failure
            pytest.skip(f"Processor not reachable at {BASE_URL}: {exc}")

        if health.status_code != 200:
            pytest.skip(f"Processor unhealthy: {health.status_code}")

        count_resp = await client.get("/messages/count")
        count_resp.raise_for_status()
        initial_count = count_resp.json()["count"]

        console.print(
            ":satellite: Awaiting Chatwoot webhook... send a message via the widget to trigger one."
        )

        message, current_count = await _wait_for_new_message(client, initial_count)

        console.print(f":inbox_tray: Raw persisted message: {message}")

        validated = Message.model_validate(message)
        title = (
            "📣 Conversation Created"
            if message.get("content") == "[conversation_created]"
            else "📨 Parsed Message"
        )
        _pretty_print_message(validated, title=title)

        latest_message = message

        if message.get("content") == "[conversation_created]":
            console.print(":bell: Conversation created detected; awaiting first message...")
            try:
                followup, current_count = await _wait_for_new_message(client, current_count)
            except AssertionError:
                console.print(
                    ":warning: No message arrived after conversation creation within the timeout window."
                )
            else:
                console.print(f":incoming_envelope: Raw persisted message: {followup}")
                validated = Message.model_validate(followup)
                _pretty_print_message(validated, title="✉️ Received Message")
                latest_message = followup

        assert latest_message["direction"] in {"inbound", "outbound"}
        assert latest_message["status"] in {"received", "queued", "sent", "failed"}
        assert latest_message["conversation_id"] > 0
        assert latest_message["content"]


async def _wait_for_new_message(
    client: httpx.AsyncClient, initial_count: int
) -> tuple[dict, int]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_seen = initial_count

    while time.monotonic() < deadline:
        count_resp = await client.get("/messages/count")
        count_resp.raise_for_status()
        current_count = count_resp.json()["count"]

        if current_count > last_seen:
            latest_resp = await client.get("/messages/latest")
            latest_resp.raise_for_status()
            return latest_resp.json(), current_count

        await asyncio.sleep(POLL_INTERVAL)

    raise AssertionError("Timed out waiting for Chatwoot webhook to persist a message")


def _pretty_print_message(message: Message, title: str = "📨 Parsed Message") -> None:
    tree = Tree(title, guide_style="bold cyan")
    payload = message.model_dump()

    for field, value in payload.items():
        _add_branch(tree, field, value)

    console.print(tree)


def _add_branch(parent: Tree, key: str, value: object) -> None:
    if isinstance(value, dict):
        branch = parent.add(f"🗂️ {key}")
        for sub_key, sub_value in value.items():
            _add_branch(branch, sub_key, sub_value)
    elif isinstance(value, list):
        branch = parent.add(f"📚 {key}")
        for index, item in enumerate(value):
            _add_branch(branch, f"[{index}]", item)
    else:
        parent.add(f"🔹 {key}: {value}")
