from odoo_api.product import OdooProduct
from odoo_api.warehouses import OdooWarehouse
from config_manager import secrets

odoo_warehouse = OdooWarehouse(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
)

odoo_product = OdooProduct(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
)

print(odoo_warehouse.max_production_quantity(['5959', '6211']))