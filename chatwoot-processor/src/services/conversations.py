from pathlib import Path

from env_manager import get_config, init_config
from pydantic import ValidationError
from requests import Response, request
from rich.console import Console
from rich.table import Table
from rich.traceback import install
from .api import ChatwootAPI
from src.models.conversation import (
    ConversationModel,
    ConversationSender,
    ConversationsResponse,
)

install()

console = Console()


class ChatwootConversation(ChatwootAPI):
    def __init__(
        self, account_id: int, api_access_token: str, base_url: str | None = None
    ) -> None:
        super().__init__(account_id=account_id, api_access_token=api_access_token)
        self.base_url = (base_url or "https://app.chatwoot.com").rstrip("/")

    @staticmethod
    def _coerce_response(payload: dict) -> ConversationsResponse:
        """
        Normalize Chatwoot payloads so Pydantic can parse them.

        Accepts:
        - {"data": {"meta": {...}, "payload": [...]}} (list)
        - {"meta": {...}, "payload": {...}} (single conversation)
        - Bare conversation object (id/meta/...).
        """
        working = payload.get("data", payload)

        if "payload" not in working:
            # Treat the object itself as the conversation payload.
            working = {"meta": {}, "payload": [working]}
        else:
            if not isinstance(working["payload"], list):
                working["payload"] = [working["payload"]]

        return ConversationsResponse.model_validate({"data": working})

    def get_conversations(self) -> ConversationsResponse:
        result: Response = request(
            method="GET",
            url=f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations",
            headers={"api_access_token": self.api_access_token},
        )
        result.raise_for_status()
        payload = result.json()
        return self._coerce_response(payload)

    def get_conversation(self, conversation_id: int) -> ConversationsResponse:
        result: Response = request(
            method="GET",
            url=(
                f"{self.base_url}/api/v1/accounts/"
                f"{self.account_id}/conversations/{conversation_id}"
            ),
            headers={"api_access_token": self.api_access_token},
        )
        result.raise_for_status()
        payload = result.json()
        return self._coerce_response(payload)

    def get_conversations_from_email(self, email: str) -> ConversationsResponse:
        email_lower = email.lower()
        all_conversations = self.get_conversations()
        matched: list[ConversationModel] = []

        for conv in all_conversations.data.payload:
            sender = _resolve_sender(conv)
            sender_email = sender.email.lower() if sender and sender.email else None
            if sender_email == email_lower:
                matched.append(conv)
                continue
            # fall back to message-level sender matching
            for msg in conv.messages:
                if (
                    msg.sender
                    and msg.sender.email
                    and msg.sender.email.lower() == email_lower
                ):
                    matched.append(conv)
                    break

        if not matched:
            return ConversationsResponse(
                data={
                    "meta": {"filtered_by_email": email, "count": 0},
                    "payload": [],
                }
            )

        # Build a synthetic merged conversation
        messages = [m for conv in matched for m in conv.messages]
        messages.sort(key=lambda m: m.created_at)
        sender = _resolve_sender(matched[0])
        last_message = messages[-1] if messages else None
        updated_at = (
            max((m.updated_at or m.created_at for m in messages))
            if messages
            else matched[0].updated_at
        )

        merged = ConversationModel(
            id=matched[0].id,
            uuid=matched[0].uuid,
            account_id=matched[0].account_id,
            inbox_id=matched[0].inbox_id,
            status="merged",
            created_at=matched[0].created_at,
            updated_at=updated_at,
            unread_count=sum(conv.unread_count for conv in matched),
            additional_attributes={},
            custom_attributes={},
            meta={
                "filtered_by_email": email,
                "merged_from": [conv.id for conv in matched],
            },
            sender=sender,
            messages=messages,
            last_non_activity_message=last_message,
        )

        return ConversationsResponse(
            data={
                "meta": {"filtered_by_email": email, "count": len(matched)},
                "payload": [merged],
            }
        )


def _resolve_sender(conversation) -> ConversationSender | None:
    if conversation.sender:
        return conversation.sender

    meta_sender = conversation.meta.get("sender")
    if isinstance(meta_sender, dict):
        try:
            return ConversationSender.model_validate(meta_sender)
        except ValidationError:
            pass

    for message in conversation.messages:
        if message.sender:
            return message.sender
    return None


def render_conversations(data: ConversationsResponse) -> None:
    table = Table(title="Chatwoot Conversations", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Contact", style="green")
    table.add_column("Email", style="yellow")
    table.add_column("Unread", justify="right")
    table.add_column("Last Message", overflow="fold")

    for conversation in data.data.payload:
        sender = _resolve_sender(conversation)
        contact_name = (sender.name or sender.email if sender else "") or "—"
        contact_email = sender.email if sender and sender.email else "—"
        unread = str(conversation.unread_count)
        last_message = conversation.last_non_activity_message or (
            conversation.messages[-1] if conversation.messages else None
        )
        snippet = (
            (last_message.content if last_message else "—").replace("\n", " ").strip()
        )
        if len(snippet) > 100:
            snippet = f"{snippet[:97]}..."
        table.add_row(
            str(conversation.id),
            conversation.status,
            contact_name,
            contact_email,
            unread,
            snippet,
        )

    console.print(table)
    if data.data.meta:
        meta = data.data.meta
        counts = ", ".join(
            f"{key.replace('_', ' ').capitalize()}: {value}"
            for key, value in meta.items()
        )
        console.print(f"[dim]{counts}[/dim]")


def main() -> None:
    import argparse

    PROJECT_ROOT = Path.cwd()
    CONFIG_PATH = PROJECT_ROOT / "config" / "config_vars.yaml"
    DOTENV_PATH = PROJECT_ROOT / ".env"

    init_config(CONFIG_PATH, dotenv_path=DOTENV_PATH)

    parser = argparse.ArgumentParser(
        description="Explore Chatwoot conversations via the API."
    )
    parser.add_argument(
        "--conversation-id",
        type=int,
        help="Fetch and display only the conversation matching this ID.",
    )
    parser.add_argument(
        "--from",
        dest="from_email",
        help="Fetch all conversations from a specific sender email and merge them.",
    )
    parser.add_argument(
        "--show-messages",
        action="store_true",
        help="When fetching a single conversation, show all messages.",
    )
    args = parser.parse_args()

    conversation_client = ChatwootConversation(
        get_config("CHATWOOT_ACCOUNT_ID"),
        get_config("CHATWOOT_API_KEY"),
        get_config("CHATWOOT_BASE_URL", default="https://app.chatwoot.com"),
    )
    try:
        if args.conversation_id is not None:
            conversations = conversation_client.get_conversation(args.conversation_id)
        elif args.from_email:
            conversations = conversation_client.get_conversations_from_email(
                args.from_email
            )
        else:
            conversations = conversation_client.get_conversations()
    except ValidationError as exc:
        console.print("[red]Unable to parse Chatwoot response:[/red]")
        console.print(exc)
    except Exception as exc:  # pragma: no cover - CLI error surface
        console.print(f"[red]Failed to fetch conversations: {exc}[/red]")
    else:
        render_conversations(conversations)
        if (args.conversation_id or args.from_email) and args.show_messages:
            conv = conversations.data.payload[0] if conversations.data.payload else None
            if conv:
                console.print("\n[bold]Messages[/bold]")
                agent_email = get_config("CHATWOOT_AGENT_EMAIL", default=None)
                agent_name = get_config("CHATWOOT_AGENT_NAME", default=None)
                for msg in conv.messages:
                    conv_sender = _resolve_sender(conv)
                    sender = msg.sender or conv_sender
                    outgoing = msg.message_type != 0
                    if outgoing:
                        # Prefer display name from Chatwoot, then configured agent name/email.
                        sender_label = (
                            sender.name
                            or agent_name
                            or sender.email
                            or agent_email
                            or (conv_sender.name if conv_sender else None)
                            or (conv_sender.email if conv_sender else None)
                            or "Unknown"
                        )
                    else:
                        # Incoming: prefer sender display name, then email, then contact name/email.
                        sender_label = (
                            sender.name
                            or sender.email
                            or (conv_sender.name if conv_sender else None)
                            or (conv_sender.email if conv_sender else None)
                            or "Unknown"
                        )

                    content = msg.content.strip()
                    console.print(
                        f"[cyan]{msg.created_at}[/cyan] "
                        f"[magenta]{sender_label}[/magenta]: {content}"
                    )
            else:
                console.print(
                    "[yellow]No messages found for the given filter.[/yellow]"
                )


if __name__ == "__main__":
    main()
