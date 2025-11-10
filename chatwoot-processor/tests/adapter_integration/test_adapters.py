from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.chatwoot_real import ChatwootRESTAdapter
from src.adapters.errors import ChatwootAdapterError
from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.interfaces.protocols import ChatwootAdapter
from src.models.conversation import Conversation, ConversationChannel
from src.models.message import MessageRecord, MessageStatus
from src.services.conversation_service import get_or_open_conversation
from src.services.message_dispatcher import dispatch_outbound_message


@pytest.mark.asyncio
async def test_mock_adapter_success() -> None:
	adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.9)
	response = await adapter.send_message(42, "Hello world")
	assert response["status"] == "sent"
	assert response["conversation_id"] == 42
	assert response["content"] == "Hello world"


@pytest.mark.asyncio
async def test_mock_adapter_failure() -> None:
	adapter = MockChatwootAdapter(failure_rate=1.0, random_func=lambda: 0.0)
	with pytest.raises(ChatwootAdapterError) as exc:
		await adapter.send_message(99, "Failure path")
	assert exc.value.payload["status"] == "failed"
	assert exc.value.payload["conversation_id"] == 99


@pytest.mark.asyncio
async def test_real_adapter_send_message_stub() -> None:
	captured: dict[str, object] = {}

	def handler(request: httpx.Request) -> httpx.Response:
		captured["url"] = str(request.url)
		captured["headers"] = dict(request.headers)
		captured["json"] = json.loads(request.content)
		return httpx.Response(202, json={"id": 12345})

	transport = httpx.MockTransport(handler)
	adapter = ChatwootRESTAdapter(
		"https://chatwoot.local",
		"token-123",
		"77",
		transport=transport,
	)

	response = await adapter.send_message(501, "Dispatch content")

	captured_url = captured["url"]
	assert isinstance(captured_url, str)
	assert captured_url.endswith(
		"/api/v1/accounts/77/conversations/501/messages"
	)

	headers_obj = captured["headers"]
	assert isinstance(headers_obj, dict)
	headers = {str(key).lower(): value for key, value in headers_obj.items()}
	assert headers.get("api_access_token") == "token-123"
	assert headers.get("content-type") == "application/json"

	payload = captured["json"]
	assert isinstance(payload, dict)
	assert payload == {"content": "Dispatch content"}

	assert response["status"] == "sent"
	assert response["conversation_id"] == 501
	assert response.get("id") == 12345


def test_protocol_parity_runtime_check() -> None:
	adapter = ChatwootRESTAdapter(
		"https://chatwoot.local",
		"token-abc",
		"88",
	)
	assert isinstance(adapter, ChatwootAdapter)


@pytest.mark.asyncio
async def test_dispatch_outbound_message_updates_status(
	db_session: AsyncSession,
) -> None:
	conversation = await get_or_open_conversation(
		db_session, "adapter-success", ConversationChannel.EMAIL
	)

	adapter = MockChatwootAdapter(failure_rate=0.0, random_func=lambda: 0.99)
	response = await dispatch_outbound_message(
		db_session, adapter, conversation, "Hello from dispatcher"
	)

	assert response["status"] == "sent"
	message = await _latest_message(db_session, conversation.id)
	assert message.status is MessageStatus.SENT


@pytest.mark.asyncio
async def test_dispatch_outbound_message_marks_failed_on_exception(
	db_session: AsyncSession,
) -> None:
	conversation = await get_or_open_conversation(
		db_session, "adapter-failure", ConversationChannel.WHATSAPP
	)

	class FailingAdapter:
		async def send_message(self, conversation_id: int, content: str) -> dict:
			raise RuntimeError("simulated delivery failure")

		async def fetch_incoming_messages(
			self, since: datetime | None = None
		) -> list[dict]:
			return []

	failing_adapter = FailingAdapter()

	with pytest.raises(RuntimeError):
		await dispatch_outbound_message(
			db_session, failing_adapter, conversation, "Should fail"
		)

	message = await _latest_message(db_session, conversation.id)
	assert message.status is MessageStatus.FAILED

	refreshed = await db_session.get(Conversation, conversation.id)
	assert refreshed is not None
	assert refreshed.is_active


async def _latest_message(
	session: AsyncSession, conversation_id: int
) -> MessageRecord:
	result = await session.execute(
		select(MessageRecord)
		.where(MessageRecord.conversation_id == conversation_id)
		.order_by(MessageRecord.id.desc())
		.limit(1)
	)
	return result.scalars().one()
