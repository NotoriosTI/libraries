from src.odoo_api.product import OdooProduct

odoo_product = OdooProduct(
    database="test",
    dotenv_path = "/Users/bastianibanez/work/libraries/odoo-api/.env"
    )
skus = odoo_product.get_skus_by_name("Aceite de Argán Natural")
print(skus)