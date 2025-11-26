Chatwoot Processor
==================

A small Python helper that talks directly to the Chatwoot REST API. It can list and inspect conversations (optionally filtered by sender email) and send outbound messages either to a specific conversation or by creating/reusing a conversation for an email address. Everything is driven from the CLI and configured via `env-manager`.

Features
--------

- Rich CLI explorer for Chatwoot conversations with optional message output and sender filtering.
- Message dispatcher that can reply to the latest conversation for an email or start a new one when none exists.
- Strongly typed Pydantic models for Chatwoot conversation payloads.
- Centralised configuration via `config/config_vars.yaml` using `env-manager`.

Project Layout
--------------

```
config/config_vars.yaml  # env-manager variable map
src/
  env_manager.py         # thin proxy around env-manager helpers
  models/conversation.py # Pydantic models for Chatwoot responses
  services/api.py        # shared base storing auth credentials
  services/conversations.py      # conversation fetch/merge + CLI renderer
  services/message_dispatcher.py # outbound send/reply CLI
```

Requirements
------------

- Python 3.13
- [Poetry](https://python-poetry.org/)
- A Chatwoot account with API access and at least one email inbox

Setup
-----

1) Install dependencies:

```bash
poetry install
```

2) Create a `.env` file in the repo root (or export the variables directly). `env-manager` will map these to the names used in the code:

```env
CHATWOOT_PROCESSOR_TOKEN=<api_access_token>    # required
CHATWOOT_PROCESSOR_ACCOUNT_ID=<account_id>     # required
CHATWOOT_BASE_URL=https://app.chatwoot.com     # optional override
CHATWOOT_EMAIL_INBOX_ID=<email_inbox_id>       # needed when creating conversations
CHATWOOT_AGENT_EMAIL=<agent_email>             # optional, used for display
CHATWOOT_AGENT_NAME=<agent_name>               # optional, used for display
```

Usage
-----

List and inspect conversations (renders a table with Rich):

```bash
poetry run python -m services.conversations
poetry run python -m services.conversations --conversation-id 123 --show-messages
poetry run python -m services.conversations --from user@example.com --show-messages
```

Send a message (creates a new conversation when no `--conversation-id` is given; falls back to `CHATWOOT_EMAIL_INBOX_ID` if `--inbox-id` is omitted):

```bash
poetry run python -m services.message_dispatcher --to user@example.com --message "Hello!" --inbox-id 1
poetry run python -m services.message_dispatcher --conversation-id 123 --to user@example.com --message "Following up"
poetry run python -m services.message_dispatcher --reply --to user@example.com --message "Reply using latest thread"
```

Programmatic example:

```python
from services.message_dispatcher import MessageDispatcher
from env_manager import get_config, init_config

init_config("config/config_vars.yaml")

dispatcher = MessageDispatcher(
    get_config("CHATWOOT_ACCOUNT_ID"),
    get_config("CHATWOOT_API_KEY"),
    get_config("CHATWOOT_BASE_URL"),
)

conversation = dispatcher.send_message("user@example.com", "Hello!", inbox_id=1)
print(conversation)
```

Notes
-----

- The CLI commands load configuration on import, so run them from the repository root (where `.env` lives).
- HTTP errors from Chatwoot raise immediately; payload shape issues surface as Pydantic `ValidationError` messages for easier debugging.
