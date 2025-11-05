import asyncio
import time
from datetime import datetime
from pathlib import Path

import aiosqlite
import httpx
import pytest
from rich.console import Console

from env_manager import get_config


BASE_URL = get_config("CHATWOOT_PROCESSOR_BASE_URL")
TIMEOUT_SECONDS = int(get_config("CHATWOOT_LIVE_TEST_TIMEOUT"))
POLL_INTERVAL = float(get_config("CHATWOOT_LIVE_TEST_POLL"))
LIVE_TEST_ENABLED = bool(get_config("CHATWOOT_LIVE_TEST_ENABLED"))
SQLITE_PATH = Path(get_config("CHATWOOT_SQLITE_DB_PATH"))

console = Console()

pytestmark = pytest.mark.skipif(
    not LIVE_TEST_ENABLED,
    reason="Live SQLite ingest test disabled; set CHATWOOT_LIVE_TEST_ENABLED=1",
)


def test_live_sqlite_ingest() -> None:
    asyncio.run(_monitor_live_ingest())


async def _monitor_live_ingest() -> None:
    if not SQLITE_PATH.exists():
        pytest.skip(f"SQLite database not found at '{SQLITE_PATH}' – ensure uvicorn is running")

    console.print(
        f":magnifying_glass_tilted_left: Monitoring live SQLite ingest at {SQLITE_PATH} while polling {BASE_URL}"
    )

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        try:
            health = await client.get("/health")
        except httpx.TransportError as exc:  # pragma: no cover - external network failure
            pytest.skip(f"Processor not reachable at {BASE_URL}: {exc}")

        if health.status_code != 200:
            pytest.skip(f"Processor unhealthy: {health.status_code}")

        baseline_count = await _fetch_message_count(client)
        baseline_row = await _fetch_latest_row()

        console.print(
            ":satellite: Awaiting REAL Chatwoot webhook. Send a message via your configured widget."
        )
        if baseline_row:
            console.print(
                f":memo: Starting from message id={baseline_row['id']} conv={baseline_row['conversation_id']} "
                f"status={baseline_row['status']} at {baseline_row['timestamp']}"
            )
        else:
            console.print(":memo: No messages yet in SQLite – the next one will confirm ingest.")

        latest_row, http_payload = await _wait_for_new_ingest(client, baseline_count, baseline_row)

        console.print("\n:ballot_box_with_check: Live webhook detected and stored!")
        console.print(
            f"SQLite row -> id={latest_row['id']}, conv={latest_row['conversation_id']}, "
            f"direction={latest_row['direction']}, status={latest_row['status']}, "
            f"content={latest_row['content']!r}"
        )
        console.print(f"API latest payload -> {http_payload}")


async def _wait_for_new_ingest(client: httpx.AsyncClient, baseline_count: int, baseline_row: dict | None):
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_count = baseline_count
    last_row_id = baseline_row["id"] if baseline_row else 0

    while time.monotonic() < deadline:
        current_count = await _fetch_message_count(client)
        console.log(f"/messages/count -> {current_count} (was {last_count})")

        latest_row = await _fetch_latest_row()
        if latest_row:
            console.log(
                f"SQLite latest -> id={latest_row['id']} conv={latest_row['conversation_id']} "
                f"direction={latest_row['direction']} status={latest_row['status']}"
            )

        if current_count > last_count or (latest_row and latest_row["id"] > last_row_id):
            latest_resp = await client.get("/messages/latest")
            latest_resp.raise_for_status()
            payload = latest_resp.json()
            if latest_row is None:
                latest_row = await _fetch_latest_row()
            return latest_row, payload

        last_count = current_count
        if latest_row:
            last_row_id = latest_row["id"]
        await asyncio.sleep(POLL_INTERVAL)

    console.print(
        ":warning: Timed out waiting for live webhook. Check that Chatwoot targets the ngrok URL "
        "and that uvicorn is running with the SQLite adapter."
    )
    raise AssertionError("Timed out waiting for live webhook to hit SQLite")


async def _fetch_message_count(client: httpx.AsyncClient) -> int:
    resp = await client.get("/messages/count")
    resp.raise_for_status()
    return resp.json()["count"]


async def _fetch_latest_row() -> dict | None:
    async with aiosqlite.connect(str(SQLITE_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, conversation_id, sender, content, direction, status, timestamp
            FROM messages
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "sender": row["sender"],
            "content": row["content"],
            "direction": row["direction"],
            "status": row["status"],
            "timestamp": row["timestamp"],
        }
