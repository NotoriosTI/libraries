## Odoo Engine

Ingests operational data from Odoo into PostgreSQL and optionally generates product embeddings for semantic search. Designed for reliability at scale with chunked upserts, resumable syncs, and optional embeddings generation.

### Highlights

- Full and incremental syncs using `write_date` watermarks
- Chunked UPSERTs optimized for PostgreSQL; ORM fallback for tests
- Covers core models: products, UoMs, partners, BOMs, production orders, inventory quants, sales/purchase orders and lines
- Optional embeddings pipeline for products using OpenAI
- Uses `config-manager` for environment-aware configuration

### Installation

```bash
cd odoo-engine
poetry install
```

As a dependency via git subdirectory:

```toml
[project]
dependencies = [
  "config-manager @ git+https://github.com/NotoriosTI/libraries.git@dev#subdirectory=config-manager",
  "dev-utils @ git+https://github.com/NotoriosTI/libraries.git@dev#subdirectory=dev-utils",
]
```

### Configuration

Managed via `config-manager`. For local development create a `.env` (or use Secret Manager in production):

```env
ENVIRONMENT=local_machine

# Odoo (production)
ODOO_PROD_URL=https://your-odoo
ODOO_PROD_DB=your_db
ODOO_PROD_USERNAME=your_user
ODOO_PROD_PASSWORD=your_password

# Database
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=odoo_engine
DB_USER=postgres
DB_PASSWORD=postgres
```

Optional runtime knobs (env):

```env
ODOO_TIMEOUT=15
ODOO_CONNECT_RETRIES=3
```

### Usage

Typical usage is to wire a database `Session` and the Odoo client, then run a full or targeted sync.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from odoo_engine.odoo_client import OdooClient
from odoo_engine.sync_manager import SyncManager

engine = create_engine("postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/odoo_engine")
Session = sessionmaker(bind=engine)
session = Session()

client = OdooClient()
sync = SyncManager(session, client)
sync.full_sync()
```

Run only specific domains:

```python
sync.sync_products()
sync.sync_boms()
sync.sync_sale_orders()
```

Populate embeddings after a sync:

```python
sync.populate_product_embeddings(model="text-embedding-3-small", batch_size=100)
```

### Internals

- `odoo_engine.odoo_client.OdooClient`: robust wrapper around `odoorpc` with URL parsing, retries and timeouts
- `odoo_engine.sync_manager.SyncManager`: orchestrates batched fetches from Odoo and chunked upserts into Postgres
  - Uses incremental watermarks stored in `SyncState`
  - Falls back to per-row ORM updates when the DB is not PostgreSQL (for tests)
- `odoo_engine.models`: SQLAlchemy models for all synced tables, including `ProductEmbedding`
- `odoo_engine.embedding_generator.EmbeddingGenerator`: OpenAI-backed vector generation

### BigQuery analytics (forecasting and stock prioritization)

This project powers downstream analytics in BigQuery to forecast monthly sales and prioritize stock for production and purchasing decisions.

- Data source: the PostgreSQL database populated by Odoo Engine
- Access method: BigQuery Federated Queries via connection `notorios.us-central1.juandb-connection`
- Dataset (examples below): `notorios.sales_analytics`

Key tables and models (maintained by saved queries in BigQuery):

1) Staging from Postgres (Federated `EXTERNAL_QUERY`)
   - `stg_product`: `id`, `default_code` (SKU), `name`
   - `stg_sale_order`: `id`, `date_order`, `state`
   - `stg_sale_order_line`: `order_id`, `product_id`, `quantity`
   - `current_stock`: aggregated from `public.inventory_quant` with negatives clamped to 0 and per-product totals (`on_hand_quantity`)

2) Analytics and model training
   - `product_dim`: filtered product dimension (non-null SKUs)
   - `monthly_sales_by_product_id` (partitioned by `month_date`, clustered by `product_id`)
   - ARIMA+ model `product_arima_plus_monthly` trained on monthly sales, excluding current month, with `HOLIDAY_REGION='CL'`
   - `product_current_month_forecast`: forecast for the current month, clamped by historical min/max per product
   - `product_stock_priority`: joins current month forecast with on-hand stock to compute daily demand, `stock_days`, and `priority` in {`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`}

Operational helpers (saved queries):

- `check-forecast`: inspect the next-month forecast for a specific `product_id`
- `health-check`: connection sanity check via `SELECT 1`
- `count-priority`: count current-month products per priority bucket

Run order and scheduling (recommended):

1. Staging refresh: `create-stg-product`, `create-stg-sale-order`, `create-stg-sale-order-line`, `create-stock-data` (hourly or daily)
2. Monthly aggregation: `create-monthly-sales` (daily)
3. Model refresh: `train-arima-plus` (daily, or at least at month start)
4. Forecast materialization: `create-monthly-forecast` (daily)
5. Stock prioritization: `estimate-stock-days` (daily)

Outputs used for decisions:

- `product_stock_priority` exposes `on_hand_quantity`, `forecast_quantity`, `daily_demand`, `stock_days`, and `priority` to drive production and purchasing workflows.

Notes and next steps:

- Current pipeline prioritizes based on finished-goods on-hand vs forecast. Integrating Bill of Materials (BOM) explosion would enable component-level shortage analysis and tighter production planning. This can be added as additional staging/analytics queries over BOM and production orders.

### Testing

```bash
poetry run pytest
```

### Notes

- Requires Python >= 3.13
- For production, set `ENVIRONMENT=production` and configure secrets in Google Cloud Secret Manager via `config-manager`


