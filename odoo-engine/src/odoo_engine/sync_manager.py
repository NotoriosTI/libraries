import logging
from math import ceil
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import datetime

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
from odoo_engine.models import ProductEmbedding
from odoo_engine.embedding_generator import EmbeddingGenerator
import tiktoken

logger = logging.getLogger(__name__)
BATCH_SIZE = 5000  # Records per Odoo fetch batch
UPSERT_CHUNK = 1000  # Records per UPSERT chunk


class SyncManager:
    def __init__(self, session: Session, client):
        self.client = client
        self.session = session
        # Mapa de ID remoto de partner -> ID remoto canónico (por VAT)
        # Se construye en sync_partners() y se usa para remapear relaciones
        self.partner_remote_to_canonical = {}

    # ------------------------
    # Generic helpers
    # ------------------------
    def _upsert(self, model, data_list, unique_field="odoo_id"):
        """Chunked UPSERT into Postgres."""
        if not data_list:
            return
        # If running against Postgres use efficient INSERT ... ON CONFLICT
        dialect_name = getattr(self.session.bind.dialect, "name", None)
        if dialect_name == "postgresql":
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
        else:
            # Fallback for sqlite/tests: perform per-row upsert using ORM queries.
            total_chunks = ceil(len(data_list) / UPSERT_CHUNK)
            for i in range(total_chunks):
                chunk = data_list[i * UPSERT_CHUNK : (i + 1) * UPSERT_CHUNK]
                for row in chunk:
                    odoo_id = row.get(unique_field)
                    if odoo_id is None:
                        continue
                    existing = self.session.query(model).filter_by(odoo_id=odoo_id).one_or_none()
                    if existing:
                        # update fields
                        for k, v in row.items():
                            setattr(existing, k, v)
                        self.session.add(existing)
                    else:
                        obj = model(**row)
                        self.session.add(obj)
                self.session.commit()
                logger.info(
                    "    ✅ Fallback upsert processed chunk %d/%d for %s",
                    i + 1,
                    total_chunks,
                    model.__tablename__,
                )

    def _get_last_synced(self, model_name: str):
        row = self.session.execute(select(SyncState).where(SyncState.model_name == model_name)).scalar_one_or_none()
        return row.last_synced if row else None

    def _set_last_synced(self, model_name: str, timestamp: datetime.datetime):
        existing = self.session.execute(select(SyncState).where(SyncState.model_name == model_name)).scalar_one_or_none()
        if existing:
            existing.last_synced = timestamp
            self.session.add(existing)
        else:
            self.session.add(SyncState(model_name=model_name, last_synced=timestamp))
        self.session.commit()

    def _fetch_in_batches(self, model_name, fields, domain=None, limit=BATCH_SIZE, since=None):
        """Fetch records from Odoo in batches using offset until no more results.

        Uses the client's `search_read` wrapper. If `since` is provided, augments
        the domain to request only records with write_date > since.
        """
        domain = domain or []
        if since:
            # ensure domain is a list of tuples/lists
            # Odoo JSON RPC requires JSON-serializable values; convert datetimes to ISO strings
            try:
                if isinstance(since, datetime.datetime):
                    since_val = since.isoformat()
                else:
                    since_val = since
            except Exception:
                since_val = since

            # append a simple tuple condition (avoid nested lists which some Odoo servers reject)
            domain = list(domain) + [('write_date', '>', since_val)]

        results = []
        offset = 0
        while True:
            batch = self.client.search_read(model_name, domain=domain, fields=fields, limit=limit, offset=offset)
            if not batch:
                break
            logger.info(
                "    🟢 Fetched batch at offset %d from %s (%d records)",
                offset,
                model_name,
                len(batch),
            )
            results.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

        return results

    def _parse_write_date(self, val):
        """Parse common Odoo write_date string formats to datetime, or return None."""
        if not val:
            return None
        if isinstance(val, datetime.datetime):
            return val
        try:
            # Try ISO first
            return datetime.datetime.fromisoformat(val)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(val, fmt)
            except Exception:
                continue
        return None

    def _id_map(self, model):
        """Return dict mapping odoo_id -> local PK id for a given model."""
        rows = self.session.execute(select(model.id, model.odoo_id)).all()
        return {odoo_id: id_ for (id_, odoo_id) in rows}

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
        # Reiniciar el mapa de canónicos en cada corrida
        self.partner_remote_to_canonical = {}

        records = self._fetch_in_batches(
            "res.partner",
            [
                "id",
                "name",
                "is_company",
                "supplier_rank",
                "customer_rank",
                "email",
                "phone",
                "vat",
                "write_date",
            ],
        )

        # Separar por presencia de VAT (RUT)
        with_vat = []
        without_vat = []
        for rec in records:
            vat_val = rec.get("vat")
            if vat_val:
                # Parsear write_date para selección del más reciente
                rec["_wd"] = self._parse_write_date(rec.get("write_date"))
                with_vat.append(rec)
            else:
                without_vat.append(rec)

        # Agrupar partners por VAT y seleccionar el más reciente por write_date
        by_vat = {}
        for rec in with_vat:
            by_vat.setdefault(rec["vat"], []).append(rec)

        canonical_by_vat = {}
        for vat_val, recs in by_vat.items():
            # Ordenar descendente por write_date (None al final)
            recs.sort(key=lambda r: (r.get("_wd") or datetime.datetime.min), reverse=True)
            chosen = recs[0]
            canonical_by_vat[vat_val] = chosen
            # Mapear todos los IDs remotos del grupo al ID canónico
            for r in recs:
                self.partner_remote_to_canonical[r["id"]] = chosen["id"]

        # Los partners sin VAT se mapean a sí mismos
        for r in without_vat:
            self.partner_remote_to_canonical[r["id"]] = r["id"]

        # Preparar UPSERT sólo con: (a) canónicos por VAT, (b) sin VAT
        data = []

        # a) canónicos por VAT
        for vat_val, chosen in canonical_by_vat.items():
            wd = chosen.get("_wd")
            data.append(
                {
                    "odoo_id": chosen["id"],
                    "name": chosen.get("name"),
                    "is_company": chosen.get("is_company"),
                    "supplier_rank": chosen.get("supplier_rank", 0),
                    "customer_rank": chosen.get("customer_rank", 0),
                    "email": chosen.get("email"),
                    "phone": chosen.get("phone"),
                    # Guardar RUT (VAT). Si False/no presente, quedará NULL
                    "rut": vat_val,
                    "write_date": wd,
                }
            )

        # b) sin VAT
        for rec in without_vat:
            wd = self._parse_write_date(rec.get("write_date"))
            data.append(
                {
                    "odoo_id": rec["id"],
                    "name": rec.get("name"),
                    "is_company": rec.get("is_company"),
                    "supplier_rank": rec.get("supplier_rank", 0),
                    "customer_rank": rec.get("customer_rank", 0),
                    "email": rec.get("email"),
                    "phone": rec.get("phone"),
                    "rut": None,
                    "write_date": wd,
                }
            )

        self._upsert(Partner, data)
        logger.info(
            "✅ Synced %d Partners (canónicos por VAT + sin VAT)",
            len(data),
        )

    def sync_products(self, delete_policy="mark_inactive"):
        # Excluir productos de tipo servicio
        last = self._get_last_synced("product.product")
        records = self._fetch_in_batches(
            "product.product",
            [
                "id",
                "default_code",
                "name",
                "type",
                "detailed_type",
                "sale_ok",
                "purchase_ok",
                "uom_id",
                "write_date",
            ],
            domain=[["detailed_type", "!=" , "service"]],
            since=last,
        )

        uom_map = self._id_map(UnitOfMeasure)
        data = []
        remote_ids = set()
        for rec in records:
            remote_ids.add(rec["id"])
            wd = self._parse_write_date(rec.get("write_date"))
            data.append({
                "odoo_id": rec["id"],
                "default_code": rec.get("default_code"),
                "name": rec.get("name"),
                "type": rec.get("type"),
                "sale_ok": rec.get("sale_ok", False),
                "purchase_ok": rec.get("purchase_ok", False),
                "active": rec.get("active", True),
                "uom_id": uom_map.get(rec["uom_id"][0]) if rec.get("uom_id") else None,
                "write_date": wd,
            })

        if data:
            self._upsert(Product, data)
            logger.info("✅ Synced %d Products", len(data))

        # Persist SyncState marker
        if records:
            self._set_last_synced("product.product", datetime.datetime.utcnow())

        # Delete detection: compute local ids not present remotely
        local_rows = self.session.execute(select(Product.odoo_id)).all()
        local_ids = {r[0] for r in local_rows}
        to_delete = local_ids - remote_ids
        if to_delete:
            if delete_policy == "mark_inactive":
                self.session.query(Product).filter(Product.odoo_id.in_(to_delete)).update({"active": False}, synchronize_session='fetch')
                self.session.commit()
                # ensure session state reflects DB changes
                self.session.expire_all()
            elif delete_policy == "delete":
                self.session.query(Product).filter(Product.odoo_id.in_(to_delete)).delete(synchronize_session='fetch')
                self.session.commit()
                self.session.expire_all()
            # else: ignore

    def sync_boms(self):
        records = self._fetch_in_batches(
            "mrp.bom", ["id", "product_id", "product_qty", "product_uom_id"]
        )
        product_map = self._id_map(Product)
        uom_map = self._id_map(UnitOfMeasure)
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
                "product_qty": rec.get("product_qty", 0),
                "uom_id": uom_map.get(rec["product_uom_id"][0])
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
        bom_map = self._id_map(Bom)
        product_map = self._id_map(Product)
        uom_map = self._id_map(UnitOfMeasure)
        data = [
            {
                "odoo_id": rec["id"],
                "bom_id": bom_map.get(rec["bom_id"][0]) if rec.get("bom_id") else None,
                "component_product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
                "product_qty": rec.get("product_qty", 0),
                # Nota: el modelo BomLine no tiene columna product_uom_id, por eso no la persistimos
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
                "date_start",
                "date_finished",
                "state",
            ],
        )
        product_map = self._id_map(Product)
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
                "product_qty": rec.get("product_qty", 0),
                "state": rec.get("state"),
                "date_planned_start": rec.get("date_start"),
                "date_planned_finished": rec.get("date_finished"),
            }
            for rec in records
        ]
        self._upsert(ProductionOrder, data)
        logger.info("✅ Synced %d Production Orders", len(data))

    def sync_inventory_quants(self):
        records = self._fetch_in_batches(
            "stock.quant", ["id", "product_id", "location_id", "quantity"]
        )
        product_map = self._id_map(Product)
        data = [
            {
                "odoo_id": rec["id"],
                "product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
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
        # Excluir cotizaciones (draft/sent) y cancelados
        records = self._fetch_in_batches(
            "sale.order",
            ["id", "partner_id", "date_order", "amount_total", "state"],
            domain=[["state", "not in", ["draft", "sent", "cancel"]]],
        )
        partner_map = self._id_map(Partner)
        data = [
            {
                "odoo_id": rec["id"],
                "partner_id": (
                    partner_map.get(
                        self.partner_remote_to_canonical.get(rec["partner_id"][0], rec["partner_id"][0])
                    )
                    if rec.get("partner_id")
                    else None
                ),
                "date_order": rec.get("date_order"),
                "amount_total": rec.get("amount_total", 0),
                "state": rec.get("state"),
            }
            for rec in records
        ]
        self._upsert(SaleOrder, data)
        logger.info("✅ Synced %d Sale Orders", len(data))

    def sync_sale_order_lines(self):
        # Excluir líneas pertenecientes a cotizaciones o canceladas
        records = self._fetch_in_batches(
            "sale.order.line",
            ["id", "order_id", "product_id", "product_uom_qty", "price_unit", "state"],
            domain=[["state", "not in", ["draft", "sent", "cancel"]]],
        )
        order_map = self._id_map(SaleOrder)
        product_map = self._id_map(Product)
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": order_map.get(rec["order_id"][0]) if rec.get("order_id") else None,
                "product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
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
        partner_map = self._id_map(Partner)
        data = [
            {
                "odoo_id": rec["id"],
                "partner_id": (
                    partner_map.get(
                        self.partner_remote_to_canonical.get(rec["partner_id"][0], rec["partner_id"][0])
                    )
                    if rec.get("partner_id")
                    else None
                ),
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
        order_map = self._id_map(PurchaseOrder)
        product_map = self._id_map(Product)
        data = [
            {
                "odoo_id": rec["id"],
                "order_id": order_map.get(rec["order_id"][0]) if rec.get("order_id") else None,
                "product_id": product_map.get(rec["product_id"][0]) if rec.get("product_id") else None,
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

    # ------------------------
    # Embeddings population (post-sync)
    # ------------------------
    def populate_product_embeddings(self, model: str = "text-embedding-3-small", batch_size: int = 100):
        """
        Generate embeddings for all products with NULL embedding_id using product name.

        - Creates rows in product_embedding with the generated vector and metadata
        - Updates product.embedding_id to reference the newly created embedding row
        """
        logger.info("🧠 Populating product embeddings (post-sync)...")

        # Fetch target products
        rows = self.session.execute(
            select(Product.id, Product.name).where(
                Product.name.isnot(None), Product.embedding_id.is_(None)
            )
        ).all()

        if not rows:
            logger.info("No products pending embedding population.")
            return

        gen = EmbeddingGenerator(model=model)
        dimension = gen.get_embedding_dimension()

        total = len(rows)
        processed = 0
        total_tokens = 0
        # prepare tokenizer for token counting (tiktoken)
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            # fallback: use a utf-8 byte length estimator if tiktoken not available for model
            enc = None

        # Use PrettyLogger.progress to show batch-level progress
        from dev_utils.pretty_logger import PrettyLogger
        pretty = PrettyLogger("odoo-sync-embeddings")

        # initialize embedding progress at 0%
        pretty.progress("Embedding batches", 0, total, progress_id="embeddings")

        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            product_ids = [r[0] for r in batch]
            texts = [r[1] or "" for r in batch]

            # Count tokens for this batch using tiktoken when available
            if enc is not None:
                try:
                    batch_tokens = sum(len(enc.encode(t)) for t in texts)
                except Exception:
                    batch_tokens = sum(max(1, len(t) // 4) for t in texts)
            else:
                batch_tokens = sum(max(1, len(t) // 4) for t in texts)
            total_tokens += batch_tokens

            # Generate embeddings outside of autoflush to avoid flushing pending objects
            with self.session.no_autoflush:
                embeddings = gen.generate(texts)
                if not embeddings or len(embeddings) != len(product_ids):
                    raise RuntimeError("Embedding generation size mismatch with product batch")

                # Insert embeddings and link back to products
                embedding_objs = []
                for vec in embeddings:
                    embedding_objs.append(
                        ProductEmbedding(vector=vec, model=model, dimension=dimension)
                    )
                self.session.add_all(embedding_objs)

            # Assign IDs and update products (flush allowed here)
            self.session.flush()

            for pid, emb_obj in zip(product_ids, embedding_objs):
                prod = self.session.get(Product, pid)
                if prod is not None:
                    prod.embedding_id = emb_obj.id
                    self.session.add(prod)

            self.session.commit()
            processed += len(batch)

            # Update pretty progress bar (showing processed products and current batch size)
            current_batch_idx = i//batch_size + 1
            total_batches = total//batch_size + 1
            pretty.progress(f"Embedding batches - ({current_batch_idx}/{total_batches})", processed, total, progress_id="embeddings")

        pretty.progress("Embedding batches", processed, total, progress_id="embeddings")
        pretty.success("🧠 Product embeddings population completed", processed=processed)

        # expose total tokens counted for later summary
        try:
            self._embedding_tokens_total = int(total_tokens)
        except Exception:
            self._embedding_tokens_total = None
