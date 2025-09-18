from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from odoo_engine.models import Base
from odoo_engine.odoo_client import OdooClient
from odoo_engine.sync_manager import SyncManager

from config_manager import secrets
from dev_utils.pretty_logger import PrettyLogger


def get_pg_dsn() -> str:
    """
    Build PostgreSQL DSN from environment variables.
    Example DSN: postgresql+psycopg2://user:password@localhost:5432/mydb
    """
    user = secrets.DB_USER
    password = secrets.DB_PASSWORD
    host = secrets.DB_HOST
    port = secrets.DB_PORT
    db = secrets.JUAN_DB_NAME

    pg_dsn = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return pg_dsn


def main():
    # -----------------------
    # Database setup
    # -----------------------
    dsn = get_pg_dsn()
    engine = create_engine(dsn, echo=False, future=True)

    # Create tables if they don’t exist
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    # -----------------------
    # Odoo API client
    # -----------------------
    odoo_url = secrets.ODOO_PROD_URL
    odoo_db = secrets.ODOO_PROD_DB
    odoo_user = secrets.ODOO_PROD_USERNAME
    odoo_password = secrets.ODOO_PROD_PASSWORD

    if not all([odoo_url, odoo_db, odoo_user, odoo_password]):
        raise RuntimeError("❌ Missing required Odoo environment variables")

    odoo_client = OdooClient()

    # -----------------------
    # Run sync with progress
    # -----------------------
    logger = PrettyLogger("odoo-sync")
    steps = [
        ("UoMs", "sync_uoms"),
        ("Partners", "sync_partners"),
        ("Products", "sync_products"),
        ("BOMs", "sync_boms"),
        ("BOM Lines", "sync_bom_lines"),
        ("Production Orders", "sync_production_orders"),
        ("Inventory Quants", "sync_inventory_quants"),
        ("Sale Orders", "sync_sale_orders"),
        ("Sale Order Lines", "sync_sale_order_lines"),
        ("Purchase Orders", "sync_purchase_orders"),
        ("Purchase Order Lines", "sync_purchase_order_lines"),
    ]

    total_steps = len(steps)
    with Session() as session:
        sync = SyncManager(session, odoo_client)

        # Initialize progress bar at 0% for the whole sync
        logger.progress("Starting odoo sync", 0, total_steps, progress_id="odoo_sync")

        for idx, (name, method_name) in enumerate(steps, start=1):
            # Show the specific step currently executing in the progress bar
            # Update progress BEFORE running the step so the bar reflects the
            # current task (previous behavior logged the task after it ran).
            logger.progress(f"Odoo sync - {name}", idx, total_steps, progress_id="odoo_sync")
            getattr(sync, method_name)()

        # Post-sync: populate product embeddings
        sync.populate_product_embeddings(batch_size=64)

        # After sync, print a tree of tables and columns with row counts
        def print_db_tree(engine, logger):
            insp = inspect(engine)
            try:
                tables = insp.get_table_names(schema="public")
            except Exception:
                tables = insp.get_table_names()

            tables = sorted(tables)

            # Collect all lines first, then emit a single log entry
            lines = ["juandb tree"]
            for tbl in tables:
                # Get row count (best-effort)
                try:
                    with engine.connect() as conn:
                        rc = conn.execute(text(f'SELECT COUNT(*) FROM public."{tbl}"')).scalar()
                except Exception:
                    rc = None

                lines.append(f"  {tbl}")
                try:
                    cols = insp.get_columns(tbl, schema="public")
                except Exception:
                    cols = insp.get_columns(tbl)

                for col in cols:
                    col_name = col.get("name")
                    lines.append(f"  |__{col_name} ({rc if rc is not None else 'N/A'})")

            tree_str = "\n".join(lines)
            logger.info(tree_str)

        print_db_tree(engine, logger)

        # Embedding counts summary: number of embedding vectors and total vector values
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) AS cnt, SUM(json_array_length(vector)) AS total_dims FROM public.product_embedding"
                    )
                ).one()
                emb_count = int(row[0] or 0)
                total_dims = int(row[1] or 0)
        except Exception:
            emb_count = 0
            total_dims = 0

        avg_dim = (total_dims / emb_count) if emb_count else None
        if avg_dim:
            logger.info(f"Embeddings summary: vectors={emb_count}, total_values={total_dims}, avg_dim={avg_dim:.1f}")
        else:
            logger.info(f"Embeddings summary: vectors={emb_count}, total_values={total_dims}")

        # If SyncManager recorded token counts, print them
        try:
            tokens = getattr(sync, "_embedding_tokens_total", None)
            if tokens is not None:
                logger.info(f"Embedding token consumption (estimated, tiktoken): {tokens}")
        except Exception:
            pass

        # If --init is passed to main, also run the legacy sales loader after sync
        import sys
        if "--init" in sys.argv:
            from odoo_engine.load_legacy_sales import main as legacy_main
            logger.info("--init flag detected: running legacy sales loader")
            # Ensure legacy loader uses its default path rather than interpreting
            # the current --init arg as a CSV path. Temporarily clear argv.
            old_argv = sys.argv
            try:
                sys.argv = [old_argv[0]]
                legacy_main()
            finally:
                sys.argv = old_argv

    print("✅ Full sync completed successfully!")


if __name__ == "__main__":
    main()
