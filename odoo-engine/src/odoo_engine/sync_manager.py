import logging
from math import ceil
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from odoo_engine.models import (
    SyncState,
    Product,
    Partner,
    UnitOfMeasure,
    Bom,
    BomLine,
    ProductionOrder,
    InventoryQuant,
    SaleOrder,
    SaleOrderLine,
    PurchaseOrder,
    PurchaseOrderLine,
)

logger = logging.getLogger(__name__)
BATCH_SIZE = 5000  # Records per Odoo fetch batch
UPSERT_CHUNK = 1000  # Records per UPSERT chunk


class SyncManager:
    def __init__(self, session: Session, client):
        self.client = client
        self.session = session

    # ------------------------
    # Generic helpers
    # ------------------------
    def _upsert(self, model, data_list, unique_field="odoo_id"):
        """Chunked UPSERT into Postgres."""
        if not data_list:
            return
        total_chunks = ceil(len(data_list) / UPSERT_CHUNK)
        for i in range(total_chunks):
            chunk = data_list[i * UPSERT_CHUNK : (i + 1) * UPSERT_CHUNK]
            stmt = insert(model).values(chunk)
            update_cols = {
                c.name: c for c in stmt.excluded if c.name not in [unique_field, "id"]
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=[unique_field], set_=update_cols
            )
            self.session.execute(stmt)
            self.session.commit()
            logger.info(
                "    ✅ Upserted chunk %d/%d for %s",
                i + 1,
                total_chunks,
                model.__tablename__,
            )

    def _fetch_in_batches(self, model_name, fields, domain=None, limit=BATCH_SIZE):
        """Fetch all records from Odoo in parallel batches."""
        domain = domain or []
        total_count = self.client.odoo.env[model_name].search_count(domain)
        if total_count == 0:
            return []

        num_batches = ceil(total_count / limit)
        logger.info(
            "Fetching %d records from %s in %d batches",
            total_count,
            model_name,
            num_batches,
        )

        results = []

        def fetch_batch(batch_idx):
            offset = batch_idx * limit
            batch = self.client.search_read(
                model_name, domain=domain, fields=fields, limit=limit, offset=offset
            )
            logger.info(
                "    🟢 Fetched batch %d/%d from %s (%d records)",
                batch_idx + 1,
                num_batches,
                model_name,
                len(batch),
            )
            return batch

        max_threads = min(num_batches, 4)  # Adjust based on environment
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(fetch_batch, i) for i in range(num_batches)]
            for future in as_completed(futures):
                results.extend(future.result())

        return results

    # ------------------------
    # Individual sync methods
    # ------------------------
    def sync_uoms(self):
        records = self._fetch_in_batches("uom.uom", ["id", "name", "category_id"])
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec["name"],
                "category_id": rec["category_id"][0]
                if rec.get("category_id")
                else None,
            }
            for rec in records
        ]
        self._upsert(UnitOfMeasure, data)
        logger.info("✅ Synced %d UoMs", len(data))

    def sync_partners(self):
        records = self._fetch_in_batches(
            "res.partner", ["id", "name", "supplier_rank", "customer_rank"]
        )
        data = [
            {
                "odoo_id": rec["id"],
                "name": rec.get("name"),
                "supplier_rank": rec.get("supplier_rank", 0),
                "customer_rank": rec.get("customer_rank", 0),
            }
            for rec in records
        ]
        self._upsert(Partner, data)
        logger.info("✅ Synced %d Partners", len(data))

    def sync_products(self):
        records = self._fetch_in_batches(
            "product.product",
            ["id", "default_code", "name", "type", "sale_ok", "purchase_ok", "uom_id"],
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
        records = self._fetch_in_batches(
            "mrp.bom", ["id", "product_id", "product_qty", "product_uom_id"]
        )
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "uom_id": rec["product_uom_id"][0]
                if rec.get("product_uom_id")
                else None,
            }
            for rec in records
        ]
        self._upsert(Bom, data)
        logger.info("✅ Synced %d BOMs", len(data))

    def sync_bom_lines(self):
        records = self._fetch_in_batches(
            "mrp.bom.line",
            ["id", "bom_id", "product_id", "product_qty", "product_uom_id"],
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
        self._upsert(BomLine, data)
        logger.info("✅ Synced %d BOM Lines", len(data))

    def sync_production_orders(self):
        records = self._fetch_in_batches(
            "mrp.production",
            [
                "id",
                "product_id",
                "product_qty",
                "date_planned_start",
                "date_planned_finished",
                "state",
            ],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "state": rec.get("state"),
                "date_planned_start": rec.get("date_planned_start"),
                "date_planned_finished": rec.get("date_planned_finished"),
            }
            for rec in records
        ]
        self._upsert(ProductionOrder, data)
        logger.info("✅ Synced %d Production Orders", len(data))

    def sync_inventory_quants(self):
        records = self._fetch_in_batches(
            "stock.quant", ["id", "product_id", "location_id", "quantity"]
        )
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "location_id": rec["location_id"][0]
                if rec.get("location_id")
                else None,
                "quantity": rec.get("quantity", 0),
            }
            for rec in records
        ]
        self._upsert(InventoryQuant, data)
        logger.info("✅ Synced %d Inventory Quants", len(data))

    def sync_sale_orders(self):
        records = self._fetch_in_batches(
            "sale.order", ["id", "partner_id", "date_order", "amount_total", "state"]
        )
        data = [
            {
                "odoo_id": rec["id"],
                "partner_id": rec["partner_id"][0] if rec.get("partner_id") else None,
                "date_order": rec.get("date_order"),
                "amount_total": rec.get("amount_total", 0),
                "state": rec.get("state"),
            }
            for rec in records
        ]
        self._upsert(SaleOrder, data)
        logger.info("✅ Synced %d Sale Orders", len(data))

    def sync_sale_order_lines(self):
        records = self._fetch_in_batches(
            "sale.order.line",
            ["id", "order_id", "product_id", "product_uom_qty", "price_unit"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": rec["order_id"][0] if rec.get("order_id") else None,
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_uom_qty", 0),
                "unit_price": rec.get("price_unit", 0),
            }
            for rec in records
        ]
        self._upsert(SaleOrderLine, data)
        logger.info("✅ Synced %d Sale Order Lines", len(data))

    def sync_purchase_orders(self):
        records = self._fetch_in_batches(
            "purchase.order",
            ["id", "partner_id", "date_order", "amount_total", "state"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "partner_id": rec["partner_id"][0] if rec.get("partner_id") else None,
                "date_order": rec.get("date_order"),
                "amount_total": rec.get("amount_total", 0),
                "state": rec.get("state"),
            }
            for rec in records
        ]
        self._upsert(PurchaseOrder, data)
        logger.info("✅ Synced %d Purchase Orders", len(data))

    def sync_purchase_order_lines(self):
        records = self._fetch_in_batches(
            "purchase.order.line",
            ["id", "order_id", "product_id", "product_qty", "price_unit"],
        )
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": rec["order_id"][0] if rec.get("order_id") else None,
                "product_id": rec["product_id"][0] if rec.get("product_id") else None,
                "quantity": rec.get("product_qty", 0),
                "unit_price": rec.get("price_unit", 0),
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
