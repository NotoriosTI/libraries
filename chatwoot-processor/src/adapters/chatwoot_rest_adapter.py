from __future__ import annotations

from typing import Any, Dict

import httpx

from env_manager import get_config

from src.interfaces.protocols import MessageDeliveryClient
from src.models.message import Message


class ChatwootRESTAdapter(MessageDeliveryClient):
    """Real Chatwoot REST client for delivering outbound messages."""

    def __init__(self) -> None:
        self.api_key: str = get_config("CHATWOOT_API_KEY")
        self.account_id: int = int(get_config("CHATWOOT_ACCOUNT_ID"))
        base_url = get_config("CHATWOOT_BASE_URL")
        self.base_url: str = base_url.rstrip("/") if base_url else ""
        self._headers: Dict[str, Any] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api_access_token": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        self.last_response_status: int | None = None
        self.last_response_body: str | None = None

    async def send_message(self, msg: Message) -> bool:
        url = (
            f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/"
            f"{msg.conversation_id}/messages"
        )

        payload = {
            "content": msg.content,
            "message_type": "outgoing",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self._headers)
            except httpx.HTTPError as exc:  # pragma: no cover - network failure
                print(
                    f"[ChatwootREST] Delivery failed for msg={msg.id}: {exc}"  # noqa: T201
                )
                self.last_response_status = None
                self.last_response_body = str(exc)
                return False

        self.last_response_status = response.status_code
        self.last_response_body = response.text
        success = response.is_success
        print(  # noqa: T201
            "[ChatwootREST] Delivery "
            f"{'succeeded' if success else 'failed'} for msg={msg.id} "
            f"status={response.status_code} body={response.text}"
        )
        return success
