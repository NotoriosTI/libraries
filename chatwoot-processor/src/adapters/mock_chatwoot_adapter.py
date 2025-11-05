from __future__ import annotations

import asyncio
import itertools
import logging
from datetime import datetime, timezone
from random import random
from typing import Any, Callable

from src.adapters.errors import ChatwootAdapterError

logger = logging.getLogger(__name__)


class MockChatwootAdapter:
    """Asynchronous mock adapter that simulates Chatwoot I/O."""

    def __init__(
        self,
        failure_rate: float = 0.2,
        *,
        latency: float = 0.05,
        random_func: Callable[[], float] | None = None,
    ) -> None:
        if not 0 <= failure_rate <= 1:
            raise ValueError("failure_rate must be between 0 and 1")
        self.failure_rate = failure_rate
        self.latency = latency
        self._random = random_func or random
        self._id_sequence = itertools.count(1)
        self._outbound_history: list[dict[str, Any]] = []
        self._incoming_messages: list[dict[str, Any]] = []

    async def send_message(self, conversation_id: int, content: str) -> dict[str, Any]:
        if conversation_id <= 0:
            raise ValueError("conversation_id must be positive")
        if not content or not content.strip():
            raise ValueError("content cannot be empty")

        await asyncio.sleep(self.latency)

        message_payload = {
            "id": next(self._id_sequence),
            "conversation_id": conversation_id,
            "content": content,
            "status": "sent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        roll = self._random()
        logger.debug(
            "Mock Chatwoot send roll=%s threshold=%s", roll, self.failure_rate
        )

        if roll < self.failure_rate:
            message_payload["status"] = "failed"
            logger.warning(
                "Mock Chatwoot simulated failure conversation_id=%s", conversation_id
            )
            raise ChatwootAdapterError(
                "Mock Chatwoot delivery failed", payload=message_payload
            )

        self._outbound_history.append(message_payload)
        logger.info(
            "Mock Chatwoot delivered conversation_id=%s message_id=%s",
            conversation_id,
            message_payload["id"],
        )
        return message_payload

    async def fetch_incoming_messages(
        self, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        logger.debug(
            "Mock Chatwoot fetching incoming messages since %s", since
        )
        if since is None:
            return list(self._incoming_messages)

        return [
            message
            for message in self._incoming_messages
            if datetime.fromisoformat(message["timestamp"]) >= since
        ]

    def queue_incoming(self, content: str, conversation_id: int = 1) -> None:
        """Enqueue a synthetic incoming message for fetch simulations."""

        message = {
            "id": next(self._id_sequence),
            "conversation_id": conversation_id,
            "content": content,
            "status": "received",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._incoming_messages.append(message)

    @property
    def outbound_history(self) -> list[dict[str, Any]]:
        return list(self._outbound_history)
