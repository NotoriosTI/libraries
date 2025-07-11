from odoo_api import OdooProduct
from config_manager import secrets

SKUS = ["6256", "8085", "6009", "6995"]

odoo_db = secrets.ODOO_PROD_DB
odoo_user = secrets.ODOO_PROD_USERNAME
odoo_password = secrets.ODOO_PROD_PASSWORD
odoo_url = secrets.ODOO_PROD_URL

product_api = OdooProduct(db=odoo_db, url=odoo_url, username=odoo_user, password=odoo_password)

print("\n--- Consulta individual ---")
for sku in SKUS:
    res = product_api.models.execute_kw(
        odoo_db, product_api.uid, odoo_password,
        'product.product', 'search_read',
        [[['default_code', '=', sku]]],
        {'fields': ['id', 'name', 'default_code', 'product_template_attribute_value_ids']}
    )
    print(f"SKU: {sku}")
    print(res)

print("\n--- Consulta batch ---")
batch_res = product_api.models.execute_kw(
    odoo_db, product_api.uid, odoo_password,
    'product.product', 'search_read',
    [[['default_code', 'in', SKUS]]],
    {'fields': ['id', 'name', 'default_code', 'product_template_attribute_value_ids']}
)
for prod in batch_res:
    print(f"SKU: {prod.get('default_code')}")
    print(prod) 