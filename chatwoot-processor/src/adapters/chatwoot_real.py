from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from src.adapters.errors import ChatwootAdapterError

logger = logging.getLogger(__name__)


class ChatwootRESTAdapter:
    """Real adapter that sends and fetches messages via Chatwoot REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        account_id: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("Chatwoot base URL must be provided")
        if not api_key:
            raise ValueError("Chatwoot API key must be provided")
        if not account_id:
            raise ValueError("Chatwoot account id must be provided")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._account_id = str(account_id)
        self._timeout = timeout
        self._transport = transport
        self._headers = {
            "Content-Type": "application/json",
            "api_access_token": self._api_key,
        }

    async def send_message(self, conversation_id: int, content: str) -> dict[str, Any]:
        if conversation_id <= 0:
            raise ValueError("conversation_id must be a positive integer")
        if not content or not content.strip():
            raise ValueError("content cannot be empty")

        endpoint = self._message_endpoint(conversation_id)
        payload = {"content": content}
        logger.debug("Dispatching message to Chatwoot endpoint=%s", endpoint)

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers,
                transport=self._transport,
            ) as client:
                response = await client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            failure_payload = self._failure_payload(
                conversation_id, content, error="timeout"
            )
            logger.exception(
                "Chatwoot send timed out for conversation_id=%s", conversation_id
            )
            raise ChatwootAdapterError("Chatwoot send timed out", payload=failure_payload) from exc
        except httpx.HTTPError as exc:
            failure_payload = self._failure_payload(
                conversation_id, content, error=str(exc)
            )
            logger.exception(
                "Chatwoot send failed due to HTTP error for conversation_id=%s",
                conversation_id,
            )
            raise ChatwootAdapterError("Chatwoot send failed", payload=failure_payload) from exc

        if not response.is_success:
            failure_payload = self._failure_payload(
                conversation_id,
                content,
                status_code=response.status_code,
                body=response.text,
            )
            logger.error(
                "Chatwoot send failed with status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise ChatwootAdapterError(
                "Chatwoot send failed", payload=failure_payload
            )

        try:
            response_payload = response.json()
        except ValueError as exc:
            failure_payload = self._failure_payload(
                conversation_id,
                content,
                status_code=response.status_code,
                body=response.text,
            )
            logger.exception("Chatwoot returned invalid JSON response")
            raise ChatwootAdapterError(
                "Invalid Chatwoot response", payload=failure_payload
            ) from exc

        result: dict[str, Any] = {
            "status": "sent",
            "conversation_id": conversation_id,
            "content": content,
        }
        if isinstance(response_payload, dict):
            result.update(response_payload)
        else:
            result["response"] = response_payload

        logger.info(
            "Chatwoot message dispatched conversation_id=%s status=%s",
            conversation_id,
            result.get("status"),
        )
        return result

    async def fetch_incoming_messages(
        self, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        logger.debug(
            "Fetching incoming messages from Chatwoot since %s (stub response)",
            since,
        )
        return []

    def _message_endpoint(self, conversation_id: int) -> str:
        return (
            f"/api/v1/accounts/{self._account_id}/conversations/"
            f"{conversation_id}/messages"
        )

    @staticmethod
    def _failure_payload(
        conversation_id: int,
        content: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "failed",
            "conversation_id": conversation_id,
            "content": content,
        }
        if status_code is not None:
            payload["status_code"] = status_code
        if body is not None:
            payload["body"] = body
        if error is not None:
            payload["error"] = error
        return payload


__all__ = ["ChatwootRESTAdapter"]
