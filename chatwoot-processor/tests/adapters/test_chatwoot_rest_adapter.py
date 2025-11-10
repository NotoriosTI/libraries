from __future__ import annotations

import json

import pytest
from httpx import MockTransport, Request, Response

from src.adapters.chatwoot_real import ChatwootRESTAdapter
from src.adapters.errors import ChatwootAdapterError


@pytest.mark.asyncio
async def test_rest_adapter_sends_payload_to_expected_endpoint() -> None:
    captured: dict[str, str] = {}

    async def _handler(request: Request) -> Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("api_access_token")
        captured["body"] = request.content.decode()
        return Response(200, json={"status": "sent", "id": 99})

    adapter = ChatwootRESTAdapter(
        "https://chatwoot.example.com",
        "token-123",
        "55",
        transport=MockTransport(_handler),
    )

    result = await adapter.send_message(7, "Hello integration")

    assert result["status"] == "sent"
    assert result["id"] == 99
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/accounts/55/conversations/7/messages"
    assert captured["auth"] == "token-123"
    assert json.loads(captured["body"]) == {"content": "Hello integration"}


@pytest.mark.asyncio
async def test_rest_adapter_raises_error_on_non_success_response() -> None:
    async def _handler(request: Request) -> Response:
        return Response(422, text="unprocessable")

    adapter = ChatwootRESTAdapter(
        "https://chatwoot.example.com",
        "token-123",
        "55",
        transport=MockTransport(_handler),
    )

    with pytest.raises(ChatwootAdapterError) as excinfo:
        await adapter.send_message(7, "Hello failure")

    payload = excinfo.value.payload
    assert payload["status"] == "failed"
    assert payload["status_code"] == 422
    assert payload["body"] == "unprocessable"
    assert payload["conversation_id"] == 7
