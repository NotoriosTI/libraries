from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from env_manager import get_config, init_config
from pydantic import ValidationError
from requests import Response, request
from rich.console import Console
from rich.traceback import install

from chatwoot_processor.models.conversation import ConversationsResponse
from .conversations import ChatwootConversation

install()

console = Console()


class MessageDispatcher(ChatwootConversation):
    """
    Dispatch messages via Chatwoot.

    - send_message: send to conversation_id if given; otherwise reuse latest
      conversation for the email, or create a new one if none exist.
    - reply: always targets the latest conversation for the email; creates
      a new conversation if none exist.
    """

    def __init__(self, account_id: int, api_access_token: str, base_url: str) -> None:
        super().__init__(account_id=account_id, api_access_token=api_access_token)
        self.base_url = base_url.rstrip("/")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "api_access_token": self.api_access_token,
        }

    def send_message(
        self,
        to_email: str,
        content: str,
        inbox_id: int,
        conversation_id: Optional[int] = None,
    ) -> ConversationsResponse:
        if conversation_id:
            self._post_message(conversation_id, content)
            return self.get_conversation(conversation_id)

        # Intentional: sending without --reply creates a new thread even if one exists.
        return self._create_conversation_and_send(to_email, content, inbox_id=inbox_id)

    def reply(
        self, to_email: str, content: str, inbox_id: Optional[int] = None
    ) -> ConversationsResponse:
        existing = self.get_conversations_from_email(to_email)
        if existing.data.payload:
            target_id = existing.data.payload[0].id
            self._post_message(target_id, content)
            return self.get_conversation(target_id)
        created = self._create_conversation_and_send(
            to_email, content, inbox_id=inbox_id
        )
        return created

    def _post_message(self, conversation_id: int, content: str) -> None:
        url = (
            f"{self.base_url}/api/v1/accounts/"
            f"{self.account_id}/conversations/{conversation_id}/messages"
        )
        body: Dict[str, Any] = {
            "content": content,
            "message_type": "outgoing",
            "private": False,
            "content_type": "text",
            "content_attributes": {},
        }
        result: Response = request(
            method="POST",
            url=url,
            headers=self._headers,
            json=body,
            timeout=30,
        )
        result.raise_for_status()

    def _create_conversation_and_send(
        self, to_email: str, content: str, inbox_id: Optional[int] = None
    ) -> ConversationsResponse:
        # Prefer the dedicated email inbox id, fall back to legacy setting.
        inbox_id = (
            inbox_id
            or get_config("CHATWOOT_EMAIL_INBOX_ID", default=None)
            or get_config("CHATWOOT_INBOX_ID", default=None)
        )
        if inbox_id is None or inbox_id == "" or str(inbox_id).lower() == "none":
            raise RuntimeError(
                "CHATWOOT_EMAIL_INBOX_ID is required to create a new conversation. "
                "Set it in your environment or pass --inbox-id."
            )
        inbox_id = int(inbox_id)

        contact_id = self._ensure_contact(to_email, inbox_id)
        create_url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations"
        payload: Dict[str, Any] = {
            "source_id": str(uuid.uuid4()),
            "inbox_id": int(inbox_id),
            "contact_id": contact_id,
            "status": "open",
            "message": {
                "content": content,
                "content_type": "text",
            },
        }
        result: Response = request(
            method="POST",
            url=create_url,
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        result.raise_for_status()
        return self._coerce_response(result.json())

    def _ensure_contact(self, email: str, inbox_id: int) -> int:
        """Create or fetch a contact by email."""
        search_url = (
            f"{self.base_url}/api/v1/accounts/{self.account_id}/contacts/search"
        )
        search_result: Response = request(
            method="GET",
            url=search_url,
            headers=self._headers,
            params={"q": email},
            timeout=30,
        )
        search_result.raise_for_status()
        data = search_result.json()
        if data.get("payload"):
            return data["payload"][0]["id"]

        create_url = f"{self.base_url}/api/v1/accounts/{self.account_id}/contacts"
        create_payload = {
            "inbox_id": int(inbox_id),
            "name": email,
            "email": email,
        }
        create_result: Response = request(
            method="POST",
            url=create_url,
            headers=self._headers,
            json=create_payload,
            timeout=30,
        )
        create_result.raise_for_status()
        return create_result.json()["payload"]["contact"]["id"]


def main() -> None:
    PROJECT_ROOT = Path.cwd()
    CONFIG_PATH = PROJECT_ROOT / "config" / "config_vars.yaml"
    DOTENV_PATH = PROJECT_ROOT / ".env"

    init_config(CONFIG_PATH, dotenv_path=DOTENV_PATH)

    parser = argparse.ArgumentParser(
        description="Send or reply to Chatwoot conversations."
    )
    parser.add_argument("--to", required=True, help="Recipient email address.")
    parser.add_argument("--message", required=True, help="Message body to send.")
    parser.add_argument(
        "--conversation-id", type=int, help="Target a specific conversation ID."
    )
    parser.add_argument(
        "--inbox-id", type=int, help="Inbox ID to use when creating a new conversation."
    )
    parser.add_argument(
        "--reply",
        action="store_true",
        help="Reply using the latest conversation for this email (ignore --conversation-id).",
    )
    args = parser.parse_args()

    dispatcher = MessageDispatcher(
        get_config("CHATWOOT_ACCOUNT_ID"),
        get_config("CHATWOOT_API_KEY"),
        get_config("CHATWOOT_BASE_URL"),
    )

    try:
        if args.reply:
            conversations = dispatcher.reply(
                args.to, args.message, inbox_id=args.inbox_id
            )
        else:
            conversations = dispatcher.send_message(
                args.to, args.message, args.conversation_id, inbox_id=args.inbox_id
            )
    except ValidationError as exc:
        console.print("[red]Unable to parse Chatwoot response:[/red]")
        console.print(exc)
    except Exception as exc:  # pragma: no cover - CLI error surface
        console.print(f"[red]Failed to send message: {exc}[/red]")
    else:
        console.print("[green]Message dispatched successfully.[/green]")
        from .conversations import render_conversations

        render_conversations(conversations)


if __name__ == "__main__":
    main()
