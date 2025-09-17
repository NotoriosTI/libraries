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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from config_manager import secrets

from odoo_engine.models import Base, SaleOrder, SaleOrderLine, Product
from dev_utils.pretty_logger import PrettyLogger


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


def get_pg_dsn() -> str:
    user = secrets.DB_USER
    password = secrets.DB_PASSWORD
    host = secrets.DB_HOST
    port = secrets.DB_PORT
    db = secrets.JUAN_DB_NAME
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


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
    engine, Session = build_engine_and_session()

    total_orders = 0
    total_lines = 0
    logger = PrettyLogger("legacy-sales-loader")

    # Pre-contar filas para progreso (aprox. igual a registros)
    try:
        with open(path, "r", encoding="utf-8") as f:
            total_rows = sum(1 for _ in f)
    except Exception:
        total_rows = 0
    processed_rows = 0

    for chunk in read_csv_headerless(path, chunksize=batch_size):
        original_rows = len(chunk)
        # Limpieza básica de strings
        for col in [
            "salesinvoiceid",
            "doctype_name",
            "customer_name",
            "customer_vatid",
            "salesman_name",
            "term_name",
            "warehouse_name",
            "items_product_description",
            "items_product_sku",
            "sales_channel",
        ]:
            if col in chunk.columns:
                chunk[col] = chunk[col].astype(str).str.strip()

        # Filtrar posibles filas de cabecera presentes en archivos con header
        header_like = (
            (chunk["salesinvoiceid"] == "salesinvoiceid")
            | (chunk["items_product_sku"] == "items_product_sku")
            | (chunk["total_total"] == "total_total")
        )
        chunk = chunk[~header_like].copy()

        # Conversión numérica robusta
        for num_col in [
            "totals_net",
            "totals_vat",
            "total_total",
            "items_quantity",
            "items_unitprice",
        ]:
            if num_col in chunk.columns:
                chunk[num_col] = pd.to_numeric(chunk[num_col], errors="coerce")

        # Deduplicación por (salesinvoiceid, items_product_sku) conservando la última
        chunk_sorted = chunk.sort_values(["salesinvoiceid", "items_product_sku", "docnumber"])  # estable
        chunk_dedup = chunk_sorted.drop_duplicates(
            subset=["salesinvoiceid", "items_product_sku"], keep="last"
        ).copy()

        # Normalizaciones
        chunk_dedup["issueddate"] = pd.to_datetime(chunk_dedup["issueddate"], errors="coerce")

        with Session() as session:
            # Mapear productos por default_code (SKU) - hacer esto una sola vez por chunk
            skus = chunk_dedup["items_product_sku"].astype(str).tolist()
            product_map = product_id_map_by_default_code(session, skus)

            # Marcar si la línea tiene product_id válido
            chunk_dedup["has_valid_product"] = chunk_dedup["items_product_sku"].astype(str).map(
                lambda sku: product_map.get(sku) is not None
            )

            # Identificar órdenes con AL MENOS UNA línea inválida
            orders_any_invalid = (
                chunk_dedup.groupby("salesinvoiceid")["has_valid_product"]
                .apply(lambda s: (~s).any())
            )
            bad_orders = orders_any_invalid[orders_any_invalid].index.tolist()

            # Excluir completamente esas órdenes
            chunk_filtered = chunk_dedup[~chunk_dedup["salesinvoiceid"].isin(bad_orders)].copy()

            # Si no queda nada, continuar
            if len(chunk_filtered) == 0:
                processed_rows += original_rows
                if total_rows > 0:
                    logger.progress("Carga de ventas históricas", processed_rows, total_rows, progress_id="legacy_load")
                continue

            # Construir órdenes únicas por invoice (solo las válidas)
            orders_df = (
                chunk_filtered.sort_values(["salesinvoiceid"]).drop_duplicates(
                    subset=["salesinvoiceid"], keep="last"
                )
            )

            orders_payload: List[dict] = []
            for _, row in orders_df.iterrows():
                so_odoo_id = deterministic_negative_id(str(row["salesinvoiceid"]))
                orders_payload.append(
                    {
                        "odoo_id": so_odoo_id,
                        "partner_id": None,
                        "date_order": row["issueddate"],
                        "amount_total": float(row["total_total"]) if pd.notna(row["total_total"]) else 0.0,
                        "state": "done",
                    }
                )

            upsert_sale_orders(session, orders_payload)
            total_orders += len(orders_payload)

            # Mapear order_id locales por odoo_id
            order_id_map = id_map_by_odoo_id(session, SaleOrder)

            # Construir líneas: mantener el guard para no insertar product_id NULL
            lines_payload: List[dict] = []
            for _, row in chunk_filtered.iterrows():
                so_odoo_id = deterministic_negative_id(str(row["salesinvoiceid"]))
                sol_odoo_id = deterministic_negative_id(str(row["salesinvoiceid"]), str(row["items_product_sku"]) or "")
                order_id = order_id_map.get(so_odoo_id)
                product_id = product_map.get(str(row["items_product_sku"]))

                if product_id is None:
                    continue  # mantener el guard

                lines_payload.append({
                    "odoo_id": sol_odoo_id,
                    "order_id": order_id,
                    "product_id": product_id,
                    "product_uom_id": None,
                    "quantity": float(row["items_quantity"]) if pd.notna(row["items_quantity"]) else 0.0,
                    "unit_price": float(row["items_unitprice"]) if pd.notna(row["items_unitprice"]) else 0.0,
                })

            upsert_sale_order_lines(session, lines_payload)
            total_lines += len(lines_payload)

        # Progreso
        processed_rows += original_rows
        if total_rows > 0:
            logger.progress("Carga de ventas históricas", processed_rows, total_rows, progress_id="legacy_load")

    return total_orders, total_lines


def main():
    # Default path
    default_path = Path(__file__).resolve().parent.parent / "data" / "ventas_historico.csv"

    # If provided, use the first CLI arg as path, otherwise default
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    if not csv_path.exists() or not csv_path.is_file():
        print(f"Archivo CSV inválido: {csv_path}")
        sys.exit(1)

    orders, lines = process_csv(csv_path)
    print(f"✅ Carga histórica completada. Órdenes procesadas: {orders}, Líneas procesadas: {lines}")


if __name__ == "__main__":
    main()


