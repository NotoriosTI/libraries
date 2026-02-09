# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Build & Run Commands

```bash
# Install dependencies
poetry install

# Run full sync (CLI entry point)
poetry run sync

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/odoo-sync/test_product_variants.py

# Run only integration tests (requires real Odoo credentials)
RUN_ODOO_INTEGRATION=1 poetry run pytest -m integration -vs

# Skip integration tests (default)
poetry run pytest -m "not integration"
```

## Architecture Overview

**odoo-engine** syncs operational data from Odoo (via XML-RPC/odoorpc) into PostgreSQL, with optional OpenAI embeddings for product search. Python 3.13+, SQLAlchemy 2.0, managed with Poetry.

### Source layout

```
src/odoo_engine/
├── sync_manager/
│   ├── main.py                 # Entry point (poetry run sync)
│   ├── sync_manager.py         # SyncManager — core sync orchestration
│   ├── models.py               # SQLAlchemy declarative models
│   ├── embedding_generator.py  # OpenAI embedding generation
│   ├── transform.py            # Odoo data transforms
│   └── validate_sync.py        # Post-sync validation
├── utils/
│   ├── odoo_client.py          # OdooClient wrapper around odoorpc
│   └── psql_client.py          # PostgreSQL DSN builder (get_pg_dsn)
├── db_client/
└── sale_order_manager/
```

### Sync pipeline

`main.py` → creates engine, tables, `OdooClient`, and `SyncManager(session, client)`, then runs the 12-step pipeline in FK-dependency order:

1. UoMs
2. Partners (deduplicated by VAT)
3. Products (with variant attributes in name)
4. BOMs
5. BOM Lines
6. Production Orders
7. Inventory Quants
8. Daily Stock History
9. Sale Orders
10. Sale Order Lines
11. Purchase Orders
12. Purchase Order Lines
13. *Post-sync:* Product Embeddings

### Database backend

- **Production:** PostgreSQL with `INSERT ... ON CONFLICT` chunked upserts (1 000 rows/chunk).
- **Tests:** In-memory SQLite with ORM-based fallback in `_upsert()`.

## Key Patterns

- **Incremental sync:** `SyncState` table stores `last_synced` watermark per Odoo model. `_fetch_in_batches()` filters by `write_date > watermark`.
- **Chunked upsert:** `_upsert(model, data_list, unique_field="odoo_id")` inserts in 1 000-row chunks; PostgreSQL path uses raw `INSERT ... ON CONFLICT DO UPDATE`, SQLite path uses ORM merge.
- **Batch fetching:** 5 000 records per Odoo RPC call (`BATCH_SIZE`).
- **Partner VAT deduplication:** `partner_remote_to_canonical` maps duplicate Odoo partner IDs to a single canonical ID chosen by lowest `odoo_id` per VAT.
- **Product variant name composition:** Base name + variant attributes fetched from `product.template.attribute.value` → `"Aceite de coco (100ml, Orgánico)"`.
- **Odoo `False` → `None` coercion:** Odoo returns `False` for empty numeric/string fields. Use `rec.get("field") or None` to coerce to `None`.
- **Delete detection:** `sync_products(delete_policy="mark_inactive")` compares local vs remote IDs; supports `mark_inactive` (default), `delete`, or `ignore`.

## Testing Conventions

- **Framework:** pytest
- **Database fixtures:** Each test file defines its own `in_memory_session` fixture using `create_engine("sqlite:///:memory:")` + `Base.metadata.create_all()`.
- **OdooClient mocking:** Use `MagicMock()` for `client.search_read`, `client.read`, `client.get_product_variant_attributes`. For bypassing `__init__`: `OdooClient.__new__(OdooClient)`.
- **Integration marker:** `@pytest.mark.integration` — requires `RUN_ODOO_INTEGRATION=1` env var and real Odoo credentials.
- **Factory helpers:** e.g. `make_client_returning_products()` in `test_incremental_sync.py`.
- **Test location:** `tests/odoo-sync/` for sync-related tests.

## Configuration

Secrets and credentials are managed by `config-manager` (reads from `.env` locally, Google Cloud Secret Manager in production).

**Required env vars:**
- `ENVIRONMENT` — `local_machine` or `production`
- `ODOO_PROD_URL`, `ODOO_PROD_DB`, `ODOO_PROD_USERNAME`, `ODOO_PROD_PASSWORD`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

**Optional knobs:**
- `ODOO_TIMEOUT` (default 15s)
- `ODOO_CONNECT_RETRIES` (default 3, with exponential backoff)

## Coding Conventions

- `snake_case` for functions and variables, `PascalCase` for classes.
- Prefix internal/private functions with `_` (e.g. `_upsert`, `_fetch_in_batches`).
- Strict typing throughout; Python 3.13+ features are fine.
- Google-style docstrings.
- **Avoid try/except** — fix root causes instead of catching exceptions.
- Never hardcode secrets; use `config-manager` / env vars.
- All imports at the top of the file.
- Use descriptive variable names with auxiliary verbs.
- Prefer `async def` for I/O-bound operations; minimize blocking I/O.
- All changes should be **additive and non-destructive** — no column/table/data deletions in migrations (use `ADD COLUMN IF NOT EXISTS`).
