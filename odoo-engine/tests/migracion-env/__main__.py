from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from odoo_engine.sync_manager.models import Base
from odoo_engine.utils import OdooClient, get_pg_dsn
from odoo_engine.sync_manager.sync_manager import SyncManager

#from config_manager import secrets
from env_manager import init_config, get_config, require_config
from dev_utils.pretty_logger import PrettyLogger

init_config(
    "config/config_vars.yaml",
    secret_origin=None, 
    gcp_project_id=None,
    strict=None,
    dotenv_path=None,
    debug=False,
)
def main():

    odoo_url = get_config("ODOO_PROD_URL")
    odoo_db = get_config("ODOO_PROD_DB")
    odoo_user = get_config("ODOO_PROD_USERNAME")
    odoo_password = get_config("ODOO_PROD_PASSWORD")


if __name__ == "__main__":
    main()
