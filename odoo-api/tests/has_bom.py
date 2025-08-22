from odoo_api.product import OdooProduct
from config_manager import secrets


def test_has_bom():
    odoo_product = OdooProduct(
        db=secrets.ODOO_PROD_DB,
        url=secrets.ODOO_PROD_URL,
        username=secrets.ODOO_PROD_USERNAME,
        password=secrets.ODOO_PROD_PASSWORD
    )

    assert odoo_product.has_bom("6769") is True
    assert odoo_product.has_bom("7218") is True
    assert odoo_product.has_bom("8053") is False
    assert odoo_product.has_bom("9112") is False


if __name__ == "__main__":
    test_has_bom()