from datetime import UTC, datetime, timedelta
from pathlib import Path

from rich.console import Console
import pytest
from pytest import MonkeyPatch
from env_manager import get_config, init_config

from chatwoot_processor.models.conversation import ConversationMessage, Direction
from chatwoot_processor.services.conversations import ChatwootConversation

console = Console()


def test_direction_is_computed_for_inbound_and_outbound_messages() -> None:
    inbound = ConversationMessage(
        id=1,
        conversation_id=99,
        content="Hello",
        account_id=1,
        inbox_id=2,
        message_type=0,  # Chatwoot incoming
        created_at=datetime.now(UTC),
        private=False,
        status="received",
    )

    outbound = ConversationMessage(
        id=2,
        conversation_id=99,
        content="Hi back",
        account_id=1,
        inbox_id=2,
        message_type=1,  # Chatwoot outgoing
        created_at=datetime.now(UTC),
        private=False,
        status="sent",
    )

    assert inbound.direction is Direction.inbound
    assert outbound.direction is Direction.outbound

    inbound_dump = inbound.model_dump()
    outbound_dump = outbound.model_dump()
    assert inbound_dump["direction"] == "inbound"
    assert outbound_dump["direction"] == "outbound"

    console.print("[green]Inbound message parsed[/green]", inbound_dump)
    console.print("[blue]Outbound message parsed[/blue]", outbound_dump)


def test_latest_conversation_direction_by_email(monkeypatch: MonkeyPatch) -> None:
    """Ensure direction is set when fetching the latest conversation by sender email."""

    now = datetime.now(UTC)
    later = now + timedelta(seconds=1)
    inbox_id = 123

    payload = {
        "data": {
            "meta": {},
            "payload": [
                {
                    "id": 99,
                    "uuid": "abc",
                    "account_id": 1,
                    "inbox_id": inbox_id,
                    "status": "open",
                    "created_at": now,
                    "updated_at": later,
                    "unread_count": 0,
                    "sender": {"id": 5, "email": "user@example.com"},
                    "messages": [
                        {
                            "id": 10,
                            "conversation_id": 99,
                            "content": "Hi",
                            "account_id": 1,
                            "inbox_id": inbox_id,
                            "message_type": 0,
                            "created_at": now,
                            "private": False,
                            "status": "received",
                        },
                        {
                            "id": 11,
                            "conversation_id": 99,
                            "content": "Hello back",
                            "account_id": 1,
                            "inbox_id": inbox_id,
                            "message_type": 1,
                            "created_at": later,
                            "private": False,
                            "status": "sent",
                        },
                    ],
                }
            ],
        }
    }

    class FakeResponse:
        status_code = 200

        def json(self):
            return payload

        def raise_for_status(self):
            return None

    # Patch the requests.request function used inside ChatwootConversation
    monkeypatch.setattr(
        "chatwoot_processor.services.conversations.request", lambda **_: FakeResponse()
    )

    client = ChatwootConversation(account_id=1, api_access_token="token")
    conversations = client.get_conversations_from_email("user@example.com")

    assert conversations.data.payload, "No conversations returned"
    conv = conversations.data.payload[0]
    last_message = conv.messages[-1]

    assert conv.inbox_id == inbox_id
    assert last_message.direction is Direction.outbound
    assert last_message.model_dump()["direction"] == "outbound"

    console.print("[green]Filtered conversation[/green]", conv.id, conv.inbox_id)
    console.print("[cyan]Latest message direction[/cyan]", last_message.direction)


def test_live_conversation_direction_from_chatwoot() -> None:
    """
    Integration sanity check against a real Chatwoot conversation.

    Relies on env-manager loading config/config_vars.yaml and .env to provide:
    - CHATWOOT_LIVE_TEST_ENABLED=1
    - CHATWOOT_LIVE_CONVERSATION_ID=<an existing conversation id>
    - CHATWOOT_API_KEY / CHATWOOT_ACCOUNT_ID / CHATWOOT_BASE_URL
    """

    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "config" / "config_vars.yaml"
    dotenv_path = project_root / ".env"
    init_config(config_path, dotenv_path=dotenv_path)

    if not get_config("CHATWOOT_LIVE_TEST_ENABLED", default=False):
        pytest.skip("CHATWOOT_LIVE_TEST_ENABLED is not set")

    conversation_id = int(get_config("CHATWOOT_LIVE_CONVERSATION_ID", default=0) or 0)
    if conversation_id <= 0:
        pytest.skip("CHATWOOT_LIVE_CONVERSATION_ID is not configured")

    client = ChatwootConversation(
        get_config("CHATWOOT_ACCOUNT_ID"),
        get_config("CHATWOOT_API_KEY"),
        get_config("CHATWOOT_BASE_URL", default="https://app.chatwoot.com"),
    )

    response = client.get_conversation(conversation_id)
    if not response.data.payload:
        pytest.skip(f"No conversation returned for id={conversation_id}")

    conversation = response.data.payload[0]
    messages = client.get_conversation_messages(conversation.id)
    if not messages:
        pytest.skip(f"No messages returned for conversation id={conversation_id}")

    console.print("[green]Live conversation[/green]", conversation.id, conversation.inbox_id)
    for msg in messages:
        snippet = msg.content.replace("\n", " ").strip()
        if len(snippet) > 80:
            snippet = f"{snippet[:77]}..."
        console.print(
            f"[cyan]msg {msg.id}[/cyan] "
            f"[magenta]{msg.direction.value}[/magenta]: {snippet}"
        )

    assert all(msg.direction in (Direction.inbound, Direction.outbound) for msg in messages)
