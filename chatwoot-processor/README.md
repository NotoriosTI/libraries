Chatwoot Processor (Mock)
=========================

An async FastAPI microservice that sits between Chatwoot webhooks and provider‑side message processing. Phase 1.2 focuses on a local, dependency‑free simulation that mirrors the production architecture while wiring real Chatwoot webhook payloads and configuration management through `env-manager`.

Features
--------

- Fully async FastAPI app with background worker that dequeues outbound messages and simulates delivery.
- In‑memory mock database implementing the message reader/writer protocols.
- Mock Chatwoot adapter for printing outbound delivery attempts (configurable failure rate).
- Real Chatwoot webhook payload parsing, including conversation creation events.
- Centralised configuration via `env-manager` (`.env` + optional GCP Secret Manager).
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
poetry run pytest tests/mock tests/chatwoot_widget
```

Test groups:

- `tests/mock/test_message_flow.py` — legacy Phase 1.1 payload coverage.
- `tests/chatwoot_widget/test_chatwoot_webhook.py` — structured Chatwoot payloads (message + conversation_created + outbound worker checks).
- `tests/chatwoot_widget/test_live_webhook.py` — optional integration that listens for real webhooks, prints stored messages with Rich tree formatting, and validates schema.

To execute the live test:

1. Ensure the FastAPI app is running locally on the same port you expose via ngrok.
2. Point Chatwoot’s webhook integration at `https://<ngrok-subdomain>.ngrok.io/webhook/chatwoot`.
3. Run:

   ```bash
   CHATWOOT_LIVE_TEST_ENABLED=1 poetry run pytest -vs tests/chatwoot_widget/test_live_webhook.py
   ```

4. Trigger a message from the Chatwoot widget. The test prints both the conversation_created record and the first actual message.

Configuration Notes
-------------------

- Configuration is loaded during the FastAPI lifespan startup via `env-manager` (`config/config_vars.yaml`), and the resulting values (`CHATWOOT_API_KEY`, `CHATWOOT_ACCOUNT_ID`, `CHATWOOT_BASE_URL`, `PORT`) are accessible through `env_manager.get_config` and cached on `app.state.settings`.
- The outbound worker poll interval and mock Chatwoot failure rate can be tuned in code (`MockChatwootAdapter(failure_rate=...)`, `OutboundWorker(..., poll_interval=...)`).

Extending / Integrating
-----------------------

- Swap `MockDBAdapter` for a real persistence layer by implementing the `MessageReader` and `MessageWriter` protocols from `src/interfaces/protocols.py`.
- Replace `MockChatwootAdapter` with a real API client by keeping the same method signature (`async def send_message(msg: Message) -> bool`).
- Filter out conversation_created entries downstream by checking for `content == "[conversation_created]"` (or by modifying `_extract_messages_from_payload` to gate on a feature flag).
