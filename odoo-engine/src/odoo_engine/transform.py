def transform_uom(r):
    return {
        "odoo_id": r["id"],
        "name": r.get("name"),
        "category_id": r.get("category_id", [None])[0]
        if r.get("category_id")
        else None,
        "active": r.get("active"),
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


def transform_product(r):
    return {
        "odoo_id": r["id"],
        "default_code": r.get("default_code"),
        "name": r.get("name"),
        "sale_ok": r.get("sale_ok"),
        "purchase_ok": r.get("purchase_ok"),
        "active": r.get("active"),
        "uom_id": r.get("uom_id", [None])[0] if r.get("uom_id") else None,
        "type": r.get("type"),
        "barcode": r.get("barcode"),
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


def transform_partner(r):
    return {
        "odoo_id": r["id"],
        "name": r.get("name"),
        "is_company": r.get("is_company"),
        "supplier_rank": r.get("supplier_rank"),
        "customer_rank": r.get("customer_rank"),
        "email": r.get("email"),
        "phone": r.get("phone"),
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


# Similar for BOM, BOMLine, ProductionOrder, InventoryQuant
def transform_sale_order(r):
    return {
        "odoo_id": r["id"],
        "partner_id": r.get("partner_id", [None])[0] if r.get("partner_id") else None,
        "date_order": r.get("date_order"),
        "state": r.get("state"),
        "amount_total": r.get("amount_total"),
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


def transform_sale_order_line(r):
    return {
        "odoo_id": r["id"],
        "order_id": r.get("order_id", [None])[0] if r.get("order_id") else None,
        "product_id": r.get("product_id", [None])[0] if r.get("product_id") else None,
        "product_uom_id": r.get("product_uom")[0] if r.get("product_uom") else None,
        "quantity": r.get("product_uom_qty") or r.get("qty") or 0,
        "unit_price": r.get("price_unit") or 0.0,
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


def transform_purchase_order(r):
    return {
        "odoo_id": r["id"],
        "partner_id": r.get("partner_id", [None])[0] if r.get("partner_id") else None,
        "date_order": r.get("date_order"),
        "state": r.get("state"),
        "amount_total": r.get("amount_total"),
        "raw_json": r,
        "write_date": r.get("write_date"),
    }


def transform_purchase_order_line(r):
    return {
        "odoo_id": r["id"],
        "order_id": r.get("order_id", [None])[0] if r.get("order_id") else None,
        "product_id": r.get("product_id", [None])[0] if r.get("product_id") else None,
        "product_uom_id": r.get("product_uom")[0] if r.get("product_uom") else None,
        "quantity": r.get("product_qty") or 0,
        "unit_price": r.get("price_unit") or 0.0,
        "raw_json": r,
        "write_date": r.get("write_date"),
    }
