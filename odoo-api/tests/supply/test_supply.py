from env_manager import get_config
from odoo_api import OdooSupply
from rich import print

SKU = "ME0171"
QTY = 100


def _get_product_and_vendor(api: OdooSupply):
    """Busca el producto por SKU y su proveedor predeterminado."""
    products = api.models.execute_kw(
        api.db,
        api.uid,
        api.password,
        "product.product",
        "search_read",
        [[["default_code", "=", SKU]]],
        {"fields": ["id", "name", "seller_ids"], "limit": 1},
    )
    if not products:
        raise ValueError(f"No se encontró el producto con SKU {SKU}")

    product = products[0]
    seller_ids = product.get("seller_ids") or []
    if not seller_ids:
        raise ValueError(
            f"El producto {SKU} no tiene proveedores configurados (seller_ids vacío)"
        )

    sellers = api.models.execute_kw(
        api.db,
        api.uid,
        api.password,
        "product.supplierinfo",
        "read",
        [seller_ids],
        {"fields": ["partner_id"]},
    )

    valid_vendor_id = None
    for seller in sellers:
        candidate = seller.get("partner_id")
        vendor_id = candidate[0] if isinstance(candidate, (list, tuple)) else candidate
        vendor = api.models.execute_kw(
            api.db,
            api.uid,
            api.password,
            "res.partner",
            "read",
            [[vendor_id]],
            {"fields": ["name", "supplier_rank"]},
        )[0]
        if vendor.get("supplier_rank", 0) > 0:
            valid_vendor_id = vendor_id
            break

    if not valid_vendor_id:
        raise ValueError(f"No se encontró un proveedor válido (supplier_rank>0) para el producto {SKU}")

    return product["id"], valid_vendor_id


def create_rfq_for_sku():
    supply = OdooSupply(
        url=get_config("ODOO_TEST_URL"),
        db=get_config("ODOO_TEST_DB"),
        username=get_config("ODOO_TEST_USERNAME"),
        password=get_config("ODOO_TEST_PASSWORD"),
    )

    product_id, vendor_id = _get_product_and_vendor(supply)
    print(
        f"Creando RFQ para SKU {SKU} (product_id={product_id}) con proveedor {vendor_id} y qty={QTY}"
    )

    rfq = supply.create_rfq(
        vendor_id=vendor_id,
        order_lines=[
            {"product_id": product_id, "product_qty": QTY},
        ],
        rfq_values={"origin": f"test_supply.py SKU {SKU}"},
    )
    print({"created_rfq": rfq})
    return rfq


if __name__ == "__main__":
    create_rfq_for_sku()
