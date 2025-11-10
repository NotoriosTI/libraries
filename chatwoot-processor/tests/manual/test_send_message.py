from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

import httpx
import pytest

from env_manager import init_config, get_config

init_config("config/config_vars.yaml")

pytestmark = pytest.mark.skip(reason="Manual test – execute this file directly.")

DEFAULT_MESSAGE = "Manual Chatwoot processor verification ping."


async def _dispatch_message(recipient: str, message: str) -> dict[str, Any]:
    base_url = os.environ.get("CHATWOOT_PROCESSOR_BASE_URL") or get_config(
        "CHATWOOT_PROCESSOR_BASE_URL"
    )
    channel = _infer_channel(recipient)
    payload = {
        "user_identifier": recipient,
        "channel": channel,
        "content": message,
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        response = await client.post("/outbound/send", json=payload)
        response.raise_for_status()
        return response.json()


def _infer_channel(identifier: str) -> str:
    if "@" in identifier:
        return "email"
    return "whatsapp"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual WhatsApp/email outbound test for the Chatwoot processor."
    )
    parser.add_argument(
        "number",
        metavar="NUMBER",
        help="Recipient identifier (WhatsApp phone number or email address).",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=DEFAULT_MESSAGE,
        help="Message to send (defaults to a short verification ping).",
    )
    return parser.parse_args()


async def _main_async(recipient: str, message: str) -> None:
    result = await _dispatch_message(recipient, message)
    print("Conversation ID:", result.get("conversation_id"))
    print("Adapter response:", result.get("response"))


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_main_async(args.number, args.message))
