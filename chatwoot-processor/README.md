Chatwoot Processor
==================

An async FastAPI microservice that sits between Chatwoot webhooks and provider‑side message processing. Phases 1 and 2 are complete: the app now ingests real Chatwoot payloads, guarantees a single active conversation per sender/channel, persists messages in the Phase 2 schema, and dispatches outbound replies via the adapter factory while staying dependency-light for local development.

Features
--------

- Fully async FastAPI app backed by Alembic-managed Postgres schema (with SQLite fallback for local tests).
- Phase 2 conversation/message models with strict status transitions and per-sender locking to avoid duplicate active conversations.
- `/webhook/chatwoot` + `/outbound/send` endpoints that persist inbound payloads and dispatch outbound replies transactionally through the adapter factory.
- Mock and REST Chatwoot adapters (failure injection, latency simulation, HTTP transport override) selected via `get_chatwoot_adapter(env)`.
- Centralised configuration via `env-manager` (`.env` + optional GCP Secret Manager) wired into the FastAPI lifespan.
- Monitoring routes (`/messages/count`, `/messages/latest`) that read from the canonical schema for quick sanity checks.

Project Layout
--------------

```
src/
  adapters/         # Mock + REST Chatwoot clients and adapter factory
  db/               # Async SQLAlchemy engine/session helpers + metadata
  models/           # SQLAlchemy models + Pydantic DTOs
  routers/          # Health, webhook ingest, outbound dispatch, monitoring
  services/         # Conversation lifecycle + outbound dispatcher logic
tests/
  mock/             # FastAPI lifespan + adapter stubs smoke test
  chatwoot_widget/  # Structured webhook + optional live flows
  phase2_*          # Schema + conversation logic regression suites
  webhook_flow/     # Phase 2 E2E flows (webhook + outbound)
config/
  config_vars.yaml  # env-manager variable map
```

Requirements
------------

- Python 3.13
- [Poetry](https://python-poetry.org/) for dependency management
- `env-manager` (installed via Poetry) for configuration loading
- (Optional) [ngrok](https://ngrok.com/) for exposing the FastAPI server to Chatwoot during live tests

Installation & Setup
--------------------

1. Install dependencies:

   ```bash
   poetry install
   ```

2. Create a `.env` file (or configure GCP Secret Manager through `env-manager`) with at least:

   ```env
   CHATWOOT_PROCESSOR_TOKEN=<chatwoot_access_token>
   CHATWOOT_PROCESSOR_ACCOUNT_ID=<chatwoot_account_id>
   CHATWOOT_PROCESSOR_PORT=8000
   # Optional override:
   CHATWOOT_BASE_URL=https://app.chatwoot.com
   ```

   `env-manager` validates required entries at startup based on `config/config_vars.yaml`.

3. (Optional) If you plan to run the live webhook test, keep ngrok ready:

   ```bash
   ngrok http 8000
   ```

Quickstart
----------

Launch the mock processor:

```bash
poetry run uvicorn src.main:app --reload --port 8000
```

Available endpoints:

- `GET /health` — basic liveness check.
- `POST /webhook/chatwoot` — resolves senders, opens/reattaches conversations, and persists inbound messages with status `received`.
- `POST /outbound/send` — dispatches queued outbound content via the adapter factory, promoting statuses to `sent`/`failed`.
- `GET /messages/count` and `GET /messages/latest` — expose contents of the store for tests/monitoring.

Webhook & End-to-End Flow
-------------------------

`POST /webhook/chatwoot` ingests raw Chatwoot webhooks, normalises the payload, resolves the sender, and guarantees a single active conversation per `(identifier, channel)` pair before persisting an inbound message. Minimal payload example:

```json
{
   "inbox": {"channel_type": "whatsapp"},
   "contact": {"phone_number": "+15551234567"},
   "content": "New inbound message"
}
```

`POST /outbound/send` consumes queued outbound events and pushes them through the adapter selected by `get_chatwoot_adapter`. Provide a conversation id and message body; optionally set `"live": true` to request the production adapter.

```json
{
   "conversation_id": 42,
   "content": "Thanks for reaching out!",
   "live": false
}
```

Web widget traffic defaults to the email channel with the synthetic sender `test@chatwoot.widget` when `contact.email` is blank, ensuring the processor can still open a conversation and persist the message.

Test the webhook locally with:

```bash
curl -X POST http://localhost:8000/webhook/chatwoot -H "Content-Type: application/json" \
       -d '{"inbox": {"channel_type": "webwidget"}, "contact": {"email": ""}, "content": "Hello!"}'
```

Logs show database persistence, outbound delivery attempts, and transactional status transitions driven by `conversation_service` + `message_dispatcher`.

Testing
-------

Run the full suite (excluding live webhook by default):

```bash
poetry run pytest
```

Useful groups:

- `tests/webhook_flow/test_end_to_end.py` — Phase 2.4 webhook ingest + outbound dispatch integration tests.
- `tests/phase2_conversation_logic/test_logic.py` — sender resolution, conversation locking, and message rules.
- `tests/phase2_schema/test_schema.py` — Alembic migration assertions and schema diff safeguards.
- `tests/mock/test_message_flow.py` — FastAPI lifespan smoke test covering webhook ingest + outbound dispatch via the mock adapter.
- `tests/chatwoot_widget/test_chatwoot_webhook.py` — structured webhook payloads (message + conversation_created + outbound dispatch).
- `tests/chatwoot_widget/test_live_webhook.py` / `tests/chatwoot_widget/test_live_sqlite_ingest.py` — optional live webhook + DB tail utilities.

Running the live suites:

1. Start the FastAPI app locally on the port exposed via ngrok (or your tunnel of choice).
2. Point Chatwoot’s webhook integration at the tunnel URL (e.g. `https://<ngrok>.ngrok.io/webhook/chatwoot`).
3. Ensure env-manager can resolve the live settings (see **Configuration Notes**) or export them manually, then run the desired suite, for example:

   ```bash
   export CHATWOOT_LIVE_TEST_ENABLED=1
   poetry run pytest -vs tests/chatwoot_widget/test_live_webhook.py
   ```

4. Follow the prompts printed by the tests—open the widget, start a conversation, send a message, and watch the logs to confirm read/delivery transitions.

Configuration Notes
-------------------

- Configuration is loaded during the FastAPI lifespan startup via `env-manager` (`config/config_vars.yaml`). Read values anywhere in the app via `env_manager.get_config`.
- Set `DATABASE_URL` (runtime) or `TEST_DATABASE_URL` (tests) to point at the desired Postgres or SQLite database; the fallback is `sqlite+aiosqlite:///./chatwoot_processor.db`.

Database & Migrations
---------------------

- Apply the async Alembic migrations with `alembic upgrade head`; revert to a clean slate using `alembic downgrade base`.
- The database URL is resolved from `TEST_DATABASE_URL` (during tests) or `DATABASE_URL` (runtime) and defaults to a local SQLite file if neither is present.
- A partial unique index on `conversation (user_identifier, channel)` with the `WHERE is_active = true` predicate enforces a single active conversation per user/channel while allowing historical inactive records to accumulate.

Concurrency & Locking
---------------------

- `conversation_service.get_or_open_conversation` wraps each `(user_identifier, channel)` pair in an asyncio mutex before touching the database so concurrent webhooks cannot open duplicate active threads.
- Row-level locks (`SELECT … FOR UPDATE`) keep existing conversations locked while the service inspects or mutates them, pairing the in-process lock with database guarantees.
- Every write helper shares `_ensure_transaction`, so state transitions (`persist_inbound`, `persist_outbound`, `update_message_status`) occur atomically and safely rollback if the adapter raises.

Conversation Logic
------------------

- `resolve_sender` normalises Chatwoot webhook payloads to `(user_identifier, channel)` pairs, treating web widget traffic as the email channel with a fallback identity of `test@chatwoot.widget` when no email is supplied.
- `get_or_open_conversation` guarantees at most one active conversation per user/channel, deactivating any lingering records before opening a new session, while `close_active_conversations` can be used to force closures for deterministic tests.
- `persist_inbound` and `persist_outbound` gate message creation to active conversations, storing UTC timestamps and defaulting statuses to `received` and `queued`, respectively.
- `update_message_status` enforces tight transitions—`received → read` for inbound, `queued → sent | failed` for outbound—raising `ValueError` on invalid state changes to preserve auditability.

Extending / Integrating
-----------------------

- Reuse `src.db.session.get_async_sessionmaker()` (or `get_session()`) plus the helpers in `src/services.conversation_service` for any background jobs that need to inspect or mutate conversations/messages.
- Implement additional outbound providers by conforming to the `ChatwootAdapter` protocol (`send_message(conversation_id, content)` + `fetch_incoming_messages`).
- Use `src.adapters.get_chatwoot_adapter(env)` to obtain the appropriate adapter (mock in non-production, REST client in production) and call `dispatch_outbound_message` for a single, transactional delivery flow.
- Filter out conversation_created entries downstream by checking for `content == "[conversation_created]"` (or by modifying `_extract_messages_from_payload` to gate on a feature flag).

Adapters Integration
--------------------

- **Environment variables** — the real adapter expects `CHATWOOT_BASE_URL`, `CHATWOOT_API_KEY`, and `CHATWOOT_ACCOUNT_ID`, all resolved through `env-manager` (`config/config_vars.yaml`).
- **Factory behaviour** — `src.adapters.get_chatwoot_adapter(env)` returns the REST adapter when `env == "production"`; every other value yields the async mock adapter with simulated latency/failures.
- **Mock adapter** — configurable `failure_rate` (default `0.2`), 50 ms artificial latency, and helper methods for seeding inbound messages during tests.
- **Dispatcher example**:

   ```python
   from src.adapters import get_chatwoot_adapter
   from src.db.session import get_session
   from src.services.conversation_service import get_or_open_conversation
   from src.services.message_dispatcher import dispatch_outbound_message

   adapter = get_chatwoot_adapter(env="production")

   async with get_session() as session:
         conversation = await get_or_open_conversation(session, "+123456", "whatsapp")
         await dispatch_outbound_message(session, adapter, conversation, "Hello from Chatwoot!")
   ```

- The dispatcher wraps `persist_outbound`/`update_message_status` in explicit transactions so that queued messages promote to `sent` on success or `failed` on any adapter exception.
