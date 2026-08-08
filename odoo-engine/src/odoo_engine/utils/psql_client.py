from odoo_engine.config import secrets


def get_pg_dsn() -> str:
    user = secrets.DB_USER
    password = secrets.DB_PASSWORD
    host = secrets.DB_HOST
    port = secrets.DB_PORT
    db = secrets.JUAN_DB_NAME
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
