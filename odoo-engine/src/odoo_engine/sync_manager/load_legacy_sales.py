"""
Carga de datos históricos de ventas (no presentes en Odoo) a la nueva
estructura de base de datos en odoo-engine: `sale_order` y `sale_order_line`.

Características:
- Lee CSV sin cabecera con 18 columnas (formato histórico existente)
- Deduplicación por (salesinvoiceid, items_product_sku)
- Upsert en `sale_order` y `sale_order_line` usando ON CONFLICT(odoo_id)
- Mapeo de FKs: `sale_order_line.order_id` a PK local de `sale_order`
- Resolución de `product_id` por `default_code` (SKU), si existe; si no, NULL
- IDs determinísticos (negativos) para `odoo_id` a partir de claves del CSV

Uso:
    poetry run python -m odoo_engine.load_legacy_sales <ruta_csv>
"""

import sys
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from odoo_engine.sync_manager.models import Base, SaleOrder, SaleOrderLine, Product
from dev_utils.pretty_logger import PrettyLogger
from odoo_engine.utils import get_pg_dsn


# --------------------------- Utilidades ---------------------------

CSV_COLUMNS: List[str] = [
    "salesinvoiceid",
    "doctype_name",
    "docnumber",
    "customer_customerid",
    "customer_name",
    "customer_vatid",
    "salesman_name",
    "term_name",
    "warehouse_name",
    "totals_net",
    "totals_vat",
    "total_total",
    "items_product_description",
    "items_product_sku",
    "items_quantity",
    "items_unitprice",
    "issueddate",
    "sales_channel",
]


def deterministic_negative_id(*parts: str) -> int:
    """Genera un entero negativo determinístico (hasta 63 bits) a partir de partes de texto.

    Evita colisiones con `odoo_id` reales (positivos).
    """
    key = "::".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    as_int = int(digest[:15], 16)  # 60 bits aprox.
    return -as_int

def read_csv_headerless(path: Path, chunksize: int) -> Iterable[pd.DataFrame]:
    return pd.read_csv(path, names=CSV_COLUMNS, encoding="utf-8", chunksize=chunksize)


def build_engine_and_session():
    dsn = get_pg_dsn()
    engine = create_engine(dsn, echo=False, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return engine, Session


def id_map_by_odoo_id(session, model) -> Dict[int, int]:
    rows = session.execute(select(model.id, model.odoo_id)).all()
    return {odoo_id: id_ for (id_, odoo_id) in rows}


def product_id_map_by_default_code(session, skus: Iterable[str]) -> Dict[str, int]:
    sku_set = {str(s).strip() for s in skus if pd.notna(s) and str(s).strip()}
    if not sku_set:
        return {}
    rows = (
        session.execute(
            select(Product.id, Product.default_code).where(Product.default_code.in_(sku_set))
        ).all()
    )
    return {default_code: id_ for (id_, default_code) in rows}


def upsert_sale_orders(session, orders: List[dict]) -> None:
    if not orders:
        return
    stmt = insert(SaleOrder).values(orders)
    update_cols = {c.name: c for c in stmt.excluded if c.name not in ["odoo_id", "id"]}
    stmt = stmt.on_conflict_do_update(index_elements=["odoo_id"], set_=update_cols)
    session.execute(stmt)
    session.commit()


def upsert_sale_order_lines(session, lines: List[dict]) -> None:
    if not lines:
        return
    stmt = insert(SaleOrderLine).values(lines)
    update_cols = {c.name: c for c in stmt.excluded if c.name not in ["odoo_id", "id"]}
    stmt = stmt.on_conflict_do_update(index_elements=["odoo_id"], set_=update_cols)
    session.execute(stmt)
    session.commit()


def chunked(iterable: Iterable, size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# --------------------------- Proceso principal ---------------------------

def process_csv(path: Path, batch_size: int = 10000) -> Tuple[int, int]:
    """
    Fast path: load the entire CSV into a UNLOGGED staging table via COPY,
    then perform set-based upserts into `sale_order` and `sale_order_line`.

    This approach is dramatically faster for multi-million row files.
    """
    engine, Session = build_engine_and_session()
    logger = PrettyLogger("legacy-sales-loader")
    total_steps = 8
    progress_id = "legacy_sales_full"

    # Create staging table (UNLOGGED for speed)
    create_staging_sql = """
    CREATE UNLOGGED TABLE IF NOT EXISTS staging_legacy_sales (
        salesinvoiceid text,
        doctype_name text,
        docnumber text,
        customer_customerid text,
        customer_name text,
        customer_vatid text,
        salesman_name text,
        term_name text,
        warehouse_name text,
        totals_net numeric,
        totals_vat numeric,
        total_total numeric,
        items_product_description text,
        items_product_sku text,
        items_quantity numeric,
        items_unitprice numeric,
        issueddate text,
        sales_channel text
    );
    """

    with engine.begin() as conn:
        conn.execute(text(create_staging_sql))
        # Step 1 complete: preparación y creación de tabla staging
        logger.progress("1/8 Preparación & staging", 1, total_steps, progress_id=progress_id)

    # COPY CSV into staging (CSV has NO header)
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()

        # Detect whether the CSV includes a header row. Read the first line
        # and compare against expected column names. If a header is present,
        # use COPY ... WITH CSV HEADER to avoid type errors when loading.
        header_present = False
        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            # Normalize tokens and expected column names for robust matching
            first_cols = [c.strip().lower() for c in first_line.split(",") if c.strip()]
            expected = [c.lower() for c in CSV_COLUMNS]
            # Consider it a header if a majority of tokens match expected column names
            matches = sum(1 for c in first_cols if c in expected)
            if matches >= max(1, len(expected) // 3):
                header_present = True
            # Reset file pointer so COPY reads from the beginning
            f.seek(0)
            copy_sql = "COPY staging_legacy_sales FROM STDIN WITH CSV HEADER" if header_present else "COPY staging_legacy_sales FROM STDIN WITH CSV"
            try:
                cur.copy_expert(copy_sql, f)
            except Exception:
                # If COPY with HEADER failed but header was detected, try without header as fallback
                if header_present:
                    raw_conn.rollback()
                    f.seek(0)
                    cur.copy_expert("COPY staging_legacy_sales FROM STDIN WITH CSV", f)
                else:
                    raise

        raw_conn.commit()
        cur.close()
        # Step 2 complete: CSV cargado en staging
        logger.progress("2/8 Carga CSV a staging", 2, total_steps, progress_id=progress_id)
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()

    logger.info("✅ CSV loaded into staging table")

    # Perform set-based upserts using SQL CTEs. Steps:
    # 1) dedupe per (salesinvoiceid, items_product_sku) keeping last docnumber
    # 2) identify orders with any missing product (exclude them)
    # 3) upsert sale_order
    # 4) upsert sale_order_line

    upsert_orders_sql = text("""
    WITH dedup AS (
      SELECT DISTINCT ON (salesinvoiceid, items_product_sku) *
      FROM staging_legacy_sales
      ORDER BY salesinvoiceid, items_product_sku, docnumber DESC
    ),
    valid_lines AS (
      SELECT d.*, p.id AS product_id
      FROM dedup d
      LEFT JOIN product p ON p.default_code = d.items_product_sku
    ),
    bad_orders AS (
      SELECT salesinvoiceid FROM valid_lines GROUP BY salesinvoiceid HAVING bool_or(product_id IS NULL)
    ),
    orders_upsert AS (
      SELECT
        - (('x' || substr(md5(salesinvoiceid),1,15))::bit(60)::bigint) AS odoo_id,
        (MAX(issueddate))::timestamp AS date_order,
        (MAX(total_total))::numeric AS amount_total,
        salesinvoiceid
      FROM valid_lines
      WHERE salesinvoiceid NOT IN (SELECT salesinvoiceid FROM bad_orders)
      GROUP BY salesinvoiceid
    )
    INSERT INTO sale_order (odoo_id, partner_id, date_order, amount_total, state)
    SELECT odoo_id, NULL, date_order, amount_total, 'done' FROM orders_upsert
    ON CONFLICT (odoo_id) DO UPDATE
      SET date_order = EXCLUDED.date_order,
          amount_total = EXCLUDED.amount_total,
          state = EXCLUDED.state;
    """)

    upsert_lines_sql = text("""
    WITH dedup AS (
      SELECT DISTINCT ON (salesinvoiceid, items_product_sku) *
      FROM staging_legacy_sales
      ORDER BY salesinvoiceid, items_product_sku, docnumber DESC
    ),
    valid_lines AS (
      SELECT d.*, p.id AS product_id
      FROM dedup d
      JOIN product p ON p.default_code = d.items_product_sku
    ),
    bad_orders AS (
      SELECT salesinvoiceid FROM (
        SELECT d.*, p.id AS product_id
        FROM dedup d
        LEFT JOIN product p ON p.default_code = d.items_product_sku
      ) t GROUP BY salesinvoiceid HAVING bool_or(product_id IS NULL)
    ),
    lines_upsert AS (
      SELECT
        - (('x' || substr(md5(salesinvoiceid || items_product_sku),1,15))::bit(60)::bigint) AS odoo_id,
        (('x' || substr(md5(salesinvoiceid),1,15))::bit(60)::bigint) * -1 AS order_hash,
        p.id AS product_id,
        (items_quantity)::numeric AS quantity,
        (items_unitprice)::numeric AS unit_price,
        salesinvoiceid,
        items_product_sku
      FROM dedup d
      JOIN product p ON p.default_code = d.items_product_sku
      WHERE d.salesinvoiceid NOT IN (SELECT salesinvoiceid FROM bad_orders)
    )
    INSERT INTO sale_order_line (odoo_id, order_id, product_id, product_uom_id, quantity, unit_price)
    SELECT l.odoo_id,
           so.id AS order_id,
           l.product_id,
           NULL,
           l.quantity,
           l.unit_price
    FROM lines_upsert l
    JOIN sale_order so ON so.odoo_id = l.order_hash
    ON CONFLICT (odoo_id) DO UPDATE
      SET order_id = EXCLUDED.order_id,
          product_id = EXCLUDED.product_id,
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price;
    """)

    # Step 3: Ejecutar upsert para sale_order
    logger.progress("3/8 Upsert: sale_order (agregación por factura)", 3, total_steps, progress_id=progress_id)
    with engine.begin() as conn:
        conn.execute(upsert_orders_sql)

        # Step 4: Ejecutar upsert para sale_order_line
        logger.progress("4/8 Upsert: sale_order_line (líneas)", 4, total_steps, progress_id=progress_id)
        conn.execute(upsert_lines_sql)

        # Counts for reporting
        orders_count = conn.execute(text("SELECT COUNT(*) FROM sale_order WHERE odoo_id < 0")).scalar()
        lines_count = conn.execute(text("SELECT COUNT(*) FROM sale_order_line WHERE odoo_id < 0")).scalar()

        # Step 5: Conteos realizados
        logger.progress("5/8 Conteos realizados", 5, total_steps, progress_id=progress_id)

        # Drop staging table
        conn.execute(text("DROP TABLE IF EXISTS staging_legacy_sales;"))

        # Step 6: Staging eliminado
        logger.progress("6/8 Limpieza: staging eliminado", 6, total_steps, progress_id=progress_id)

    # Step 7: Registrar resumen final
    logger.progress("7/8 Registrando resumen final", 7, total_steps, progress_id=progress_id)
    logger.info(f"✅ Legacy sales upsert completed: orders={int(orders_count or 0)} lines={int(lines_count or 0)}")

    # Step 8: Completado
    logger.progress("8/8 Completado", 8, total_steps, progress_id=progress_id)
    return int(orders_count or 0), int(lines_count or 0)


def main():
    # Default path (data directory is at project root, not under src)
    default_path = Path(__file__).resolve().parent.parent.parent / "data" / "ventas_historico.csv"

    # If provided, use the first CLI arg as path, otherwise default
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    if not csv_path.exists() or not csv_path.is_file():
        print(f"Archivo CSV inválido: {csv_path}")
        sys.exit(1)

    orders, lines = process_csv(csv_path)
    print(f"✅ Carga histórica completada. Órdenes procesadas: {orders}, Líneas procesadas: {lines}")


if __name__ == "__main__":
    main()


