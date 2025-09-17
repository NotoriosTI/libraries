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
        for idx, (name, method_name) in enumerate(steps, start=1):
            getattr(sync, method_name)()
            logger.progress("Sincronización Odoo", idx, total_steps, progress_id="odoo_sync")

        # Post-sync: populate product embeddings
        sync.populate_product_embeddings(batch_size=100)

        # After sync, print a tree of tables and columns with row counts
        def print_db_tree(engine, logger):
            insp = inspect(engine)
            try:
                tables = insp.get_table_names(schema="public")
            except Exception:
                tables = insp.get_table_names()

            tables = sorted(tables)
            for tbl in tables:
                # Get row count (best-effort)
                try:
                    with engine.connect() as conn:
                        rc = conn.execute(text(f'SELECT COUNT(*) FROM public."{tbl}"')).scalar()
                except Exception:
                    rc = None

                logger.info(tbl)
                try:
                    cols = insp.get_columns(tbl, schema="public")
                except Exception:
                    cols = insp.get_columns(tbl)

                for col in cols:
                    col_name = col.get("name")
                    logger.info(f"  |__{col_name} ({rc if rc is not None else 'N/A'})")

        print_db_tree(engine, logger)

        # If --init is passed to main, also run the legacy sales loader after sync
        import sys
        if "--init" in sys.argv:
            from odoo_engine.load_legacy_sales import main as legacy_main
            logger.info("--init flag detected: running legacy sales loader")
            legacy_main()

    print("✅ Full sync completed successfully!")


if __name__ == "__main__":
    main()
