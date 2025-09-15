from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odoo_engine.models import Base
from odoo_engine.odoo_client import OdooClient
from odoo_engine.sync_manager import SyncManager

from config_manager import secrets


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
    # Run sync
    # -----------------------
    with Session() as session:
        sync = SyncManager(odoo_client, session)
        sync.full_sync()

    print("✅ Full sync completed successfully!")


if __name__ == "__main__":
    main()
