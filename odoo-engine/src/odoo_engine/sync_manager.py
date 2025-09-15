import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from odoo_engine.models import (
    SyncState,
    Product,
    Partner,
    UoM,
    BillOfMaterial,
    BillOfMaterialLine,
    ProductionOrder,
    InventoryQuant,
    SaleOrder,
    SaleOrderLine,
    PurchaseOrder,
    PurchaseOrderLine,
)

logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(self, client, session: Session):
        self.client = client
        self.session = session

    # ------------------------
    # Generic helpers
    # ------------------------
    def _upsert(self, model, data_list, unique_field="odoo_id"):
        """Generic UPSERT into Postgres."""
        if not data_list:
            return
        stmt = insert(model).values(data_list)
        update_cols = {
            c.name: c for c in stmt.excluded if c.name not in [unique_field, "id"]
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[unique_field],
            set_=update_cols,
        )
        self.session.execute(stmt)
        self.session.commit()

    # ------------------------
    # Individual sync methods
    # ------------------------
    def sync_uoms(self):
        records = self.client.search_read(
            "uom.uom", fields=["id", "name", "category_id"]
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec["name"],
                "category": rec["category_id"][1] if rec.get("category_id") else None,
            }
            for rec in records
        ]
        self._upsert(UoM, data)
        logger.info("✅ Synced %d UoMs", len(data))

    def sync_partners(self):
        records = self.client.search_read(
            "res.partner",
            fields=["id", "name", "supplier_rank", "customer_rank"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec["name"],
                "supplier_rank": rec.get("supplier_rank", 0),
                "customer_rank": rec.get("customer_rank", 0),
            }
            for rec in records
        ]
        self._upsert(Partner, data)
        logger.info("✅ Synced %d Partners", len(data))

    def sync_products(self):
        records = self.client.search_read(
            "product.product",
            fields=[
                "id",
                "default_code",
                "name",
                "type",
                "sale_ok",
                "purchase_ok",
                "uom_id",
            ],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "default_code": rec.get("default_code"),
                "name": rec.get("name"),
                "type": rec.get("type"),
                "sale_ok": rec.get("sale_ok", False),
                "purchase_ok": rec.get("purchase_ok", False),
                "uom_id": rec["uom_id"][0] if rec.get("uom_id") else None,
            }
            for rec in records
        ]
        self._upsert(Product, data)
        logger.info("✅ Synced %d Products", len(data))

    def sync_boms(self):
        records = self.client.search_read(
            "mrp.bom",
            fields=["id", "product_tmpl_id", "product_qty", "product_uom_id"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": rec["product_tmpl_id"][0]
                if rec.get("product_tmpl_id")
                else None,
                "quantity": rec.get("product_qty", 0),
                "uom_id": rec["product_uom_id"][0]
                if rec.get("product_uom_id")
                else None,
            }
            for rec in records
        ]
        self._upsert(BillOfMaterial, data)
        logger.info("✅ Synced %d BOMs", len(data))

    def sync_bom_lines(self):
        records = self.client.search_read(
            "mrp.bom.line",
            fields=["id", "bom_id", "product_id", "product_qty", "product_uom_id"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "bom_id": rec["bom_id"][0] if rec.get("bom_id") else None,
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "uom_id": rec["product_uom_id"][0]
                if rec.get("product_uom_id")
                else None,
            }
            for rec in records
        ]
        self._upsert(BillOfMaterialLine, data)
        logger.info("✅ Synced %d BOM Lines", len(data))

    def sync_production_orders(self):
        records = self.client.search_read(
            "mrp.production",
            fields=[
                "id",
                "name",
                "product_id",
                "product_qty",
                "date_planned_start",
                "date_finished",
            ],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec.get("name"),
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "date_planned_start": rec.get("date_planned_start"),
                "date_finished": rec.get("date_finished"),
            }
            for rec in records
        ]
        self._upsert(ProductionOrder, data)
        logger.info("✅ Synced %d Production Orders", len(data))

    def sync_inventory_quants(self):
        records = self.client.search_read(
            "stock.quant",
            fields=["id", "product_id", "location_id", "quantity"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "location": rec["location_id"][1] if rec.get("location_id") else None,
                "quantity": rec.get("quantity", 0),
            }
            for rec in records
        ]
        self._upsert(InventoryQuant, data)
        logger.info("✅ Synced %d Inventory Quants", len(data))

    def sync_sale_orders(self):
        records = self.client.search_read(
            "sale.order",
            fields=[
                "id",
                "name",
                "partner_id",
                "date_order",
                "amount_total",
                "user_id",
            ],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec["name"],
                "partner_id": rec["partner_id"][0] if rec.get("partner_id") else None,
                "date_order": rec.get("date_order"),
                "amount_total": rec.get("amount_total", 0),
                "user_id": rec["user_id"][0] if rec.get("user_id") else None,
            }
            for rec in records
        ]
        self._upsert(SaleOrder, data)
        logger.info("✅ Synced %d Sale Orders", len(data))

    def sync_sale_order_lines(self):
        records = self.client.search_read(
            "sale.order.line",
            fields=["id", "order_id", "product_id", "product_uom_qty", "price_unit"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": rec["order_id"][0] if rec.get("order_id") else None,
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_uom_qty", 0),
                "price_unit": rec.get("price_unit", 0),
            }
            for rec in records
        ]
        self._upsert(SaleOrderLine, data)
        logger.info("✅ Synced %d Sale Order Lines", len(data))

    def sync_purchase_orders(self):
        records = self.client.search_read(
            "purchase.order",
            fields=[
                "id",
                "name",
                "partner_id",
                "date_order",
                "amount_total",
                "user_id",
            ],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec["name"],
                "partner_id": rec["partner_id"][0] if rec.get("partner_id") else None,
                "date_order": rec.get("date_order"),
                "amount_total": rec.get("amount_total", 0),
                "user_id": rec["user_id"][0] if rec.get("user_id") else None,
            }
            for rec in records
        ]
        self._upsert(PurchaseOrder, data)
        logger.info("✅ Synced %d Purchase Orders", len(data))

    def sync_purchase_order_lines(self):
        records = self.client.search_read(
            "purchase.order.line",
            fields=["id", "order_id", "product_id", "product_qty", "price_unit"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": rec["order_id"][0] if rec.get("order_id") else None,
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "price_unit": rec.get("price_unit", 0),
            }
            for rec in records
        ]
        self._upsert(PurchaseOrderLine, data)
        logger.info("✅ Synced %d Purchase Order Lines", len(data))

    # ------------------------
    # Master sync
    # ------------------------
    def full_sync(self):
        logger.info("🚀 Starting full sync...")
        self.sync_uoms()
        self.sync_partners()
        self.sync_products()
        self.sync_boms()
        self.sync_bom_lines()
        self.sync_production_orders()
        self.sync_inventory_quants()
        self.sync_sale_orders()
        self.sync_sale_order_lines()
        self.sync_purchase_orders()
        self.sync_purchase_order_lines()
        logger.info("🎉 Full sync completed successfully!")
