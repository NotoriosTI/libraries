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

### Testing

```bash
poetry run pytest
```

### Notes

- Requires Python >= 3.13
- For production, set `ENVIRONMENT=production` and configure secrets in Google Cloud Secret Manager via `config-manager`


