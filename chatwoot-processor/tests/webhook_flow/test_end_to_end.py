from __future__ import annotations

import pytest
from httpx import MockTransport, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.adapters.chatwoot_real import ChatwootRESTAdapter
from src.adapters.errors import ChatwootAdapterError
from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.models.conversation import Conversation, ConversationChannel
from src.models.message import MessageDirection, MessageRecord, MessageStatus
from src.routers import outbound as outbound_router


@pytest.mark.asyncio
async def test_inbound_webhook_persists_message(
    async_client,
    session_factory: async_sessionmaker,
) -> None:
    payload = {
        "channel_type": "whatsapp",
        "contact": {"phone_number": "+15551234567"},
        "content": "Hello inbound",
    }

    response = await async_client.post("/webhook/chatwoot", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == MessageDirection.INBOUND.value
    assert body["status"] == MessageStatus.RECEIVED.value

    async with session_factory() as session:
        conversation = await session.get(Conversation, body["conversation_id"])
        assert conversation is not None
        assert conversation.user_identifier == "+15551234567"
        assert conversation.channel == ConversationChannel.WHATSAPP

        message = await session.get(MessageRecord, body["message_id"])
        assert message is not None
        assert message.content == "Hello inbound"
        assert message.status == MessageStatus.RECEIVED


@pytest.mark.asyncio
async def test_webwidget_fallback_identifies_sender(
    async_client,
    session_factory: async_sessionmaker,
) -> None:
    payload = {
        "inbox": {"channel_type": "webwidget"},
        "contact": {"email": ""},
        "content": "Widget hello",
    }

    response = await async_client.post("/webhook/chatwoot", json=payload)
    assert response.status_code == 200
    body = response.json()

    async with session_factory() as session:
        conversation = await session.get(Conversation, body["conversation_id"])
        assert conversation is not None
        assert conversation.user_identifier == "test@chatwoot.widget"
        assert conversation.channel == ConversationChannel.EMAIL


@pytest.mark.asyncio
async def test_outbound_send_transitions_to_sent(
    async_client,
    session_factory: async_sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbound_payload = {
        "channel_type": "email",
        "contact": {"email": "customer@example.com"},
        "content": "Need assistance",
    }
    inbound_response = await async_client.post("/webhook/chatwoot", json=inbound_payload)
    conversation_id = inbound_response.json()["conversation_id"]

    adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.9)
    monkeypatch.setattr(outbound_router, "get_chatwoot_adapter", lambda env: adapter)

    response = await async_client.post(
        "/outbound/send",
        json={"conversation_id": conversation_id, "content": "Sure, how can I help?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["response"]["status"] == "sent"

    async with session_factory() as session:
        result = await session.execute(
            select(MessageRecord)
            .where(
                MessageRecord.conversation_id == conversation_id,
                MessageRecord.direction == MessageDirection.OUTBOUND,
            )
            .order_by(MessageRecord.id.desc())
            .limit(1)
        )
        message = result.scalars().first()
        assert message is not None
        assert message.status == MessageStatus.SENT

    assert adapter.outbound_history
    assert adapter.outbound_history[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_mock_and_real_adapter_payload_parity() -> None:
    async def _handler(request: Request) -> Response:
        assert request.method == "POST"
        return Response(200, json={"id": 321, "status": "sent"})

    transport = MockTransport(_handler)
    real_adapter = ChatwootRESTAdapter(
        "https://chatwoot.example.com",
        "token",
        "5",
        transport=transport,
    )
    mock_adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.9)

    real_result = await real_adapter.send_message(7, "Hello parity")
    mock_result = await mock_adapter.send_message(7, "Hello parity")

    assert real_result["status"] == mock_result["status"] == "sent"
    assert real_result["conversation_id"] == mock_result["conversation_id"] == 7
    assert real_result["content"] == mock_result["content"] == "Hello parity"


@pytest.mark.asyncio
async def test_outbound_failure_marks_message_failed(
    async_client,
    session_factory: async_sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbound_payload = {
        "channel_type": "email",
        "contact": {"email": "failcase@example.com"},
        "content": "Trigger failure",
    }
    inbound_response = await async_client.post("/webhook/chatwoot", json=inbound_payload)
    conversation_id = inbound_response.json()["conversation_id"]

    class FailingAdapter:
        async def send_message(self, conversation_id: int, content: str) -> dict:
            raise ChatwootAdapterError("mock failure", payload={"status": "failed"})

    monkeypatch.setattr(outbound_router, "get_chatwoot_adapter", lambda env: FailingAdapter())

    response = await async_client.post(
        "/outbound/send",
        json={"conversation_id": conversation_id, "content": "This will fail"},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["status"] == "failed"

    async with session_factory() as session:
        result = await session.execute(
            select(MessageRecord)
            .where(
                MessageRecord.conversation_id == conversation_id,
                MessageRecord.direction == MessageDirection.OUTBOUND,
            )
            .order_by(MessageRecord.id.desc())
            .limit(1)
        )
        message = result.scalars().first()
        assert message is not None
        assert message.status == MessageStatus.FAILED

        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.is_active is True


@pytest.mark.asyncio
async def test_end_to_end_flow(async_client, session_factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    inbound_payload = {
        "channel_type": "whatsapp",
        "contact": {"phone_number": "+441234567890"},
        "content": "Hey there",
    }
    inbound_response = await async_client.post("/webhook/chatwoot", json=inbound_payload)
    data = inbound_response.json()
    conversation_id = data["conversation_id"]
    inbound_message_id = data["message_id"]

    adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.8)
    monkeypatch.setattr(outbound_router, "get_chatwoot_adapter", lambda env: adapter)

    outbound_response = await async_client.post(
        "/outbound/send",
        json={"conversation_id": conversation_id, "content": "Hello from processor"},
    )
    assert outbound_response.status_code == 200
    outbound_payload = outbound_response.json()["response"]
    assert outbound_payload["status"] == "sent"

    async with session_factory() as session:
        inbound_record = await session.get(MessageRecord, inbound_message_id)
        assert inbound_record is not None
        assert inbound_record.status == MessageStatus.RECEIVED

        outbound_result = await session.execute(
            select(MessageRecord)
            .where(
                MessageRecord.conversation_id == conversation_id,
                MessageRecord.direction == MessageDirection.OUTBOUND,
            )
            .order_by(MessageRecord.id.desc())
            .limit(1)
        )
        outbound_record = outbound_result.scalars().first()
        assert outbound_record is not None
        assert outbound_record.status == MessageStatus.SENT

    assert len(adapter.outbound_history) == 1
    assert adapter.outbound_history[0]["content"] == "Hello from processor"
