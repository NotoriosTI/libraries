Chatwoot Processor (Mock)
=========================

An async FastAPI microservice that sits between Chatwoot webhooks and provider‑side message processing. Phase 1.2 focuses on a local, dependency‑free simulation that mirrors the production architecture while wiring real Chatwoot webhook payloads and configuration management through `env-manager`.

Features
--------

- Fully async FastAPI app with background worker that dequeues outbound messages and simulates delivery.
- In‑memory mock database implementing the message reader/writer protocols.
- Mock Chatwoot adapter for printing outbound delivery attempts (configurable failure rate + async I/O simulation).
- Real Chatwoot REST adapter powered by `httpx`, selected via the adapter factory for production environments.
- Real Chatwoot webhook payload parsing, including conversation creation events.
- Centralised configuration via `env-manager` (`.env` + optional GCP Secret Manager).
- Transactional dispatcher that persists outbound messages, calls the adapter, and records `sent`/`failed` transitions deterministically.
- Monitoring routes (`/messages/count`, `/messages/latest`) for tests and manual inspection.

Project Layout
--------------

```
src/
  adapters/         # Mock DB + mock Chatwoot client
  dependencies.py   # Simple DI setters/getters used by FastAPI Depends
  models/           # Pydantic models (Message + conversation state + webhook payload)
  routers/          # Health, inbound webhook, monitoring
  workers/          # Outbound worker loop
tests/
  mock/             # Phase 1.1 message flow test (legacy payload)
  chatwoot_widget/  # Phase 1.2 structured + live webhook tests
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
- `POST /webhook/chatwoot` — accepts both Phase 1.1 mock payloads and real Chatwoot webhook bodies. Persists inbound messages (status `received`) and queues outbound ones (status `queued`).
- `GET /messages/count` and `GET /messages/latest` — expose contents of the in-memory store for tests/monitoring.

Logs show database persistence, outbound delivery attempts, and state transitions driven solely by the worker.

Testing
-------

Run the full suite (excluding live webhook by default):

```bash
poetry run pytest tests/mock tests/chatwoot_widget tests/chatwoot_delivery
```

Useful groups:

- `tests/mock/test_message_flow.py` — legacy Phase 1.1 payload flow.
- `tests/chatwoot_widget/test_chatwoot_webhook.py` — structured webhook payloads (message + conversation_created + outbound worker checks).
- `tests/chatwoot_delivery/test_synthetic_delivery.py` — synthetic outbound cycle using the worker with a patched delivery client.
- `tests/chatwoot_delivery/test_synthetic_consume.py` — synthetic inbound webhook → consume flow with detailed DB logging.
- `tests/chatwoot_widget/test_live_webhook.py` / `tests/chatwoot_widget/test_live_sqlite_ingest.py` — optional live webhook + DB tail utilities.
- `tests/chatwoot_delivery/test_live_delivery.py` / `tests/chatwoot_delivery/test_live_consume.py` — optional end-to-end outbound + inbound consume checks.

Running the live suites:

1. Start the FastAPI app locally on the port exposed via ngrok (or your tunnel of choice).
2. Point Chatwoot’s webhook integration at the tunnel URL (e.g. `https://<ngrok>.ngrok.io/webhook/chatwoot`).
3. Ensure env-manager can resolve the live settings (see **Configuration Notes**) or export them manually, then run the desired suite, for example:

   ```bash
   export CHATWOOT_LIVE_TEST_ENABLED=1
   poetry run pytest -vs tests/chatwoot_delivery/test_live_delivery.py
   ```

4. Follow the prompts printed by the tests—open the widget, start a conversation, send a message, and watch the logs to confirm read/delivery transitions.

Configuration Notes
-------------------

- Configuration is loaded during the FastAPI lifespan startup via `env-manager` (`config/config_vars.yaml`), and the resulting values (`CHATWOOT_API_KEY`, `CHATWOOT_ACCOUNT_ID`, `CHATWOOT_BASE_URL`, `CHATWOOT_PROCESSOR_BASE_URL`, `CHATWOOT_LIVE_TEST_ENABLED`, `CHATWOOT_LIVE_TEST_TIMEOUT`, `CHATWOOT_LIVE_TEST_POLL`, `CHATWOOT_SQLITE_DB_PATH`, `PORT`, etc.) are accessible through `env_manager.get_config` and cached on `app.state.settings`.
- The outbound worker poll interval can be tuned directly in code (`OutboundWorker(..., poll_interval=...)`).

Database & Migrations
---------------------

- Apply the async Alembic migrations with `alembic upgrade head`; revert to a clean slate using `alembic downgrade base`.
- The database URL is resolved from `TEST_DATABASE_URL` (during tests) or `DATABASE_URL` (runtime) and defaults to a local SQLite file if neither is present.
- A partial unique index on `conversation (user_identifier, channel)` with the `WHERE is_active = true` predicate enforces a single active conversation per user/channel while allowing historical inactive records to accumulate.

Conversation Logic
------------------

- `resolve_sender` normalises Chatwoot webhook payloads to `(user_identifier, channel)` pairs, treating web widget traffic as the email channel with a fallback identity of `test@chatwoot.widget` when no email is supplied.
- `get_or_open_conversation` guarantees at most one active conversation per user/channel, deactivating any lingering records before opening a new session, while `close_active_conversations` can be used to force closures for deterministic tests.
- `persist_inbound` and `persist_outbound` gate message creation to active conversations, storing UTC timestamps and defaulting statuses to `received` and `queued`, respectively.
- `update_message_status` enforces tight transitions—`received → read` for inbound, `queued → sent | failed` for outbound—raising `ValueError` on invalid state changes to preserve auditability.

Extending / Integrating
-----------------------

- Swap `MockDBAdapter` for a real persistence layer by implementing the `MessageReader` and `MessageWriter` protocols from `src/interfaces/protocols.py`.
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
