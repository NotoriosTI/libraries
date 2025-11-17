# Roadmap

Phases 1 and 2 are complete and production-ready. The next milestone is the LangGraph-based purchase order handler (Phase 3), followed by fulfilment automations (Phase 4).

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| **1.1** | In-memory mock processor | ✅ Completed | Mock adapters + webhook prototype. |
| **1.2** | Real Chatwoot webhook + env-manager | ✅ Completed | Live payload ingest with config management. |
| **1.3** | Database bridge (SQLite → Postgres) | ✅ Completed | Async engine + schema translate map. |
| **1.4** | Chatwoot outbound API integration | ✅ Completed | REST adapter + outbound dispatcher. |
| **2.1** | Persistent schema + models | ✅ Completed | Alembic migration `202501171200_phase2_1_comm_schema.py`. |
| **2.2** | Conversation logic + enforcement | ✅ Completed | Sender resolution, unique active conversations, locking. |
| **2.3** | Adapter integration | ✅ Completed | Mock + REST adapters wired through factory. |
| **2.4** | End-to-end flows + tests | ✅ Completed | Webhook ingest, outbound send, integration suites. |
| **3** | Purchase order handler agent | ⏳ Pending | Requires LangGraph + Odoo integrations. |
| **4** | Fulfilment automation | ⏳ Blocked | Depends on Phase 3 outputs. |

Immediate focus before Phase 3:

1. Legacy cleanup (completed in this change set).
2. Documentation + locking notes (completed).
3. Prep work for LangGraph + Odoo (next up).
