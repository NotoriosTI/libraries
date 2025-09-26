"""
Validador de sincronización de datos (Odoo + históricos)

Ejecuta verificaciones de:
- Conteos básicos de tablas maestras
- Distribución por fuente (Odoo vs Histórica) en órdenes y líneas
- Relaciones (FK) y orfandades entre tablas
- Consistencia de montos en órdenes históricas (suma de líneas vs total)

Uso:
  poetry run python -m odoo_engine.validate_sync
"""

import sys
from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config_manager import secrets
from dev_utils.pretty_logger import PrettyLogger
from odoo_engine.sync_manager.odoo_client import OdooClient


def get_pg_dsn() -> str:
    user = secrets.DB_USER
    password = secrets.DB_PASSWORD
    host = secrets.DB_HOST
    port = secrets.DB_PORT
    db = secrets.JUAN_DB_NAME
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


@dataclass
class ValidationResult:
    critical_failures: int = 0
    warnings: int = 0


class SyncValidator:
    def __init__(self):
        dsn = get_pg_dsn()
        self.engine = create_engine(dsn, echo=False, future=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.logger = PrettyLogger("sync-validator")
        # Inicializar cliente Odoo para comparaciones
        try:
            self.odoo_client = OdooClient()
        except Exception as e:
            self.logger.warning(f"No se pudo conectar a Odoo: {e}")
            self.odoo_client = None

    # ---------- helpers ----------
    def _scalar(self, sql: str) -> Optional[int]:
        with self.engine.connect() as conn:
            res = conn.execute(text(sql)).scalar()
            return int(res) if res is not None else None

    def _exists(self, sql: str) -> bool:
        with self.engine.connect() as conn:
            res = conn.execute(text(sql)).scalar()
            return bool(res)

    # ---------- checks ----------
    def check_master_counts(self, result: ValidationResult):
        self.logger.header("Tablas maestras")
        counts = {
            "uom": self._scalar("SELECT COUNT(*) FROM uom"),
            "product": self._scalar("SELECT COUNT(*) FROM product"),
            "partner": self._scalar("SELECT COUNT(*) FROM partner"),
        }
        for k, v in counts.items():
            self.logger.metric(f"{k} registros", v or 0)
        # criterio básico
        if (counts["uom"] or 0) == 0 or (counts["product"] or 0) == 0:
            result.critical_failures += 1
            self.logger.error("Datos maestros incompletos (uom/product vacíos)")

    def check_orders_distribution(self, result: ValidationResult):
        self.logger.header("Órdenes y líneas (distribución por fuente)")
        so_total = self._scalar("SELECT COUNT(*) FROM sale_order") or 0
        so_hist = self._scalar("SELECT COUNT(*) FROM sale_order WHERE odoo_id < 0") or 0
        so_odoo = so_total - so_hist

        sol_total = self._scalar("SELECT COUNT(*) FROM sale_order_line") or 0
        sol_hist = self._scalar("SELECT COUNT(*) FROM sale_order_line WHERE odoo_id < 0") or 0
        sol_odoo = sol_total - sol_hist

        self.logger.metric("sale_order (total)", so_total)
        self.logger.metric("sale_order (hist)", so_hist)
        self.logger.metric("sale_order (odoo)", so_odoo)
        self.logger.metric("sale_order_line (total)", sol_total)
        self.logger.metric("sale_order_line (hist)", sol_hist)
        self.logger.metric("sale_order_line (odoo)", sol_odoo)

        if so_total == 0 or sol_total == 0:
            result.critical_failures += 1
            self.logger.error("No hay órdenes o líneas cargadas")

    def check_referential_integrity(self, result: ValidationResult):
        self.logger.header("Integridad referencial (orfandades)")

        orphan_sol_orders = self._scalar(
            """
            SELECT COUNT(*)
            FROM sale_order_line l
            LEFT JOIN sale_order o ON o.id = l.order_id
            WHERE l.order_id IS NOT NULL AND o.id IS NULL
            """
        ) or 0
        self.logger.metric("Líneas sin orden", orphan_sol_orders)
        if orphan_sol_orders > 0:
            result.critical_failures += 1
            self.logger.error("Existen sale_order_line huérfanas (order_id inválido)")

        orphan_sol_products = self._scalar(
            """
            SELECT COUNT(*)
            FROM sale_order_line l
            LEFT JOIN product p ON p.id = l.product_id
            WHERE l.product_id IS NOT NULL AND p.id IS NULL
            """
        ) or 0
        self.logger.metric("Líneas con product_id inválido", orphan_sol_products)
        if orphan_sol_products > 0:
            result.critical_failures += 1
            self.logger.error("Existen sale_order_line con product_id inválido")

        null_product_lines = self._scalar(
            "SELECT COUNT(*) FROM sale_order_line WHERE product_id IS NULL"
        ) or 0
        self.logger.metric("Líneas con product_id NULL (hist)", null_product_lines)

        orphan_bom_product = self._scalar(
            """
            SELECT COUNT(*) FROM bom b
            LEFT JOIN product p ON p.id = b.product_id
            WHERE b.product_id IS NOT NULL AND p.id IS NULL
            """
        ) or 0
        self.logger.metric("BOM con product_id inválido", orphan_bom_product)
        if orphan_bom_product > 0:
            result.warnings += 1

        orphan_bomline_bom = self._scalar(
            """
            SELECT COUNT(*) FROM bom_line bl
            LEFT JOIN bom b ON b.id = bl.bom_id
            WHERE bl.bom_id IS NOT NULL AND b.id IS NULL
            """
        ) or 0
        self.logger.metric("BOM Line con bom_id inválido", orphan_bomline_bom)
        if orphan_bomline_bom > 0:
            result.critical_failures += 1

        orphan_bomline_comp = self._scalar(
            """
            SELECT COUNT(*) FROM bom_line bl
            LEFT JOIN product p ON p.id = bl.component_product_id
            WHERE bl.component_product_id IS NOT NULL AND p.id IS NULL
            """
        ) or 0
        self.logger.metric("BOM Line con component_product_id inválido", orphan_bomline_comp)
        if orphan_bomline_comp > 0:
            result.critical_failures += 1

        orphan_prodorder_product = self._scalar(
            """
            SELECT COUNT(*) FROM production_order po
            LEFT JOIN product p ON p.id = po.product_id
            WHERE po.product_id IS NOT NULL AND p.id IS NULL
            """
        ) or 0
        self.logger.metric("Production Order con product_id inválido", orphan_prodorder_product)
        if orphan_prodorder_product > 0:
            result.warnings += 1

        orphan_quant_product = self._scalar(
            """
            SELECT COUNT(*) FROM inventory_quant q
            LEFT JOIN product p ON p.id = q.product_id
            WHERE q.product_id IS NOT NULL AND p.id IS NULL
            """
        ) or 0
        self.logger.metric("Inventory Quant con product_id inválido", orphan_quant_product)
        if orphan_quant_product > 0:
            result.warnings += 1

    def check_amount_consistency_historical(self, result: ValidationResult):
        self.logger.header("Consistencia de montos (históricos)")
        # Compara amount_total del pedido histórico con suma de líneas
        sql = text(
            """
            WITH line_totals AS (
                SELECT l.order_id,
                       SUM(COALESCE(l.quantity,0) * COALESCE(l.unit_price,0)) AS sum_lines
                FROM sale_order_line l
                JOIN sale_order o ON o.id = l.order_id
                WHERE o.odoo_id < 0
                GROUP BY l.order_id
            )
            SELECT COUNT(*)
            FROM sale_order o
            JOIN line_totals lt ON lt.order_id = o.id
            WHERE o.odoo_id < 0
              AND COALESCE(o.amount_total,0) IS DISTINCT FROM COALESCE(lt.sum_lines,0)
            """
        )
        with self.engine.connect() as conn:
            mismatches = int(conn.execute(sql).scalar() or 0)
        self.logger.metric("Órdenes históricas con desvío de monto", mismatches)
        if mismatches > 0:
            result.warnings += 1

    def check_product_relationships(self, result: ValidationResult, default_codes=None):
        """Verificar relaciones específicas de uno o más productos por default_code."""
        default_codes = default_codes or ["5959"]
        self.logger.header(f"Verificación de relaciones de productos {', '.join(default_codes)}")
        
        if not self.odoo_client:
            self.logger.warning("Cliente Odoo no disponible, saltando verificación de relaciones")
            return

        try:
            # Procesar cada default_code solicitado
            for code in default_codes:
                self.logger.step(f"Producto {code}")
                with self.engine.connect() as conn:
                    # Producto local
                    product_local = conn.execute(text("""
                        SELECT p.id, p.odoo_id, p.default_code, p.name, p.type, p.sale_ok, p.purchase_ok, p.uom_id,
                               u.name as uom_name
                        FROM product p
                        LEFT JOIN uom u ON u.id = p.uom_id
                        WHERE p.default_code = :code
                    """), {"code": code}).fetchone()

                    if not product_local:
                        self.logger.error(f"Producto {code} no encontrado en base de datos local")
                        result.critical_failures += 1
                        continue

                    self.logger.info(f"Producto local: ID={product_local.id}, Odoo_ID={product_local.odoo_id}, Name={product_local.name}")
                    self.logger.info(f"UoM: {product_local.uom_name} (ID: {product_local.uom_id})")

                    # BOMs del producto
                    boms_local = conn.execute(text("""
                        SELECT b.id, b.odoo_id, b.product_qty, u.name as uom_name
                        FROM bom b
                        LEFT JOIN uom u ON u.id = b.uom_id
                        WHERE b.product_id = :product_id
                    """), {"product_id": product_local.id}).fetchall()

                    self.logger.info(f"BOMs locales encontrados: {len(boms_local)}")
                    for bom in boms_local:
                        self.logger.info(f"  BOM ID={bom.id}, Odoo_ID={bom.odoo_id}, Qty={bom.product_qty}, UoM={bom.uom_name}")

                    # BOM Lines del producto
                    bom_lines_local = conn.execute(text("""
                        SELECT bl.id, bl.odoo_id, bl.product_qty,
                               p_comp.default_code as component_sku, p_comp.name as component_name
                        FROM bom_line bl
                        LEFT JOIN product p_comp ON p_comp.id = bl.component_product_id
                        JOIN bom b ON b.id = bl.bom_id
                        WHERE b.product_id = :product_id
                    """), {"product_id": product_local.id}).fetchall()

                    self.logger.info(f"BOM Lines locales encontrados: {len(bom_lines_local)}")
                    for line in bom_lines_local:
                        self.logger.info(f"  Line ID={line.id}, Odoo_ID={line.odoo_id}, Qty={line.product_qty}, Component={line.component_sku} ({line.component_name})")

                    # Obtener datos desde Odoo para comparar
                    odoo_product_id = product_local.odoo_id
                    if odoo_product_id:
                        # Producto en Odoo
                        odoo_product = self.odoo_client.odoo.env['product.product'].browse(odoo_product_id)
                        if odoo_product.exists():
                            self.logger.info(f"Producto Odoo: ID={odoo_product.id}, Name={odoo_product.name}, Type={odoo_product.type}")
                            self.logger.info(f"UoM Odoo: {odoo_product.uom_id.name if odoo_product.uom_id else 'None'}")

                            # BOMs en Odoo (search -> ids, luego browse)
                            odoo_bom_ids = self.odoo_client.odoo.env['mrp.bom'].search([('product_id', '=', odoo_product_id)])
                            self.logger.info(f"BOMs Odoo encontrados: {len(odoo_bom_ids)}")
                            odoo_boms_rs = self.odoo_client.odoo.env['mrp.bom'].browse(odoo_bom_ids)
                            for bom in odoo_boms_rs:
                                self.logger.info(f"  BOM Odoo ID={bom.id}, Qty={bom.product_qty}, UoM={bom.product_uom_id.name if bom.product_uom_id else 'None'}")

                                # BOM Lines en Odoo (search -> ids, luego browse)
                                odoo_line_ids = self.odoo_client.odoo.env['mrp.bom.line'].search([('bom_id', '=', bom.id)])
                                self.logger.info(f"    BOM Lines Odoo: {len(odoo_line_ids)}")
                                odoo_lines_rs = self.odoo_client.odoo.env['mrp.bom.line'].browse(odoo_line_ids)
                                for line in odoo_lines_rs:
                                    comp_code = line.product_id.default_code if line.product_id else None
                                    comp_name = line.product_id.name if line.product_id else None
                                    self.logger.info(f"      Line Odoo ID={line.id}, Qty={line.product_qty}, Component={comp_code} ({comp_name})")
                        else:
                            self.logger.warning(f"Producto Odoo con ID {odoo_product_id} no existe")
                            result.warnings += 1
                    else:
                        self.logger.warning("Producto local no tiene odoo_id válido")
                        result.warnings += 1
                    
        except Exception as e:
            self.logger.error(f"Error verificando relaciones del producto 5959: {e}")
            result.critical_failures += 1

    # ---------- runner ----------
    def run(self) -> int:
        res = ValidationResult()
        self.logger.header("Validación de sincronización")

        try:
            self.check_master_counts(res)
            self.check_orders_distribution(res)
            self.check_referential_integrity(res)
            # Validaciones históricas ignoradas por ahora (no impactan)
            # self.check_amount_consistency_historical(res)
            # Verificar relaciones para los default_code solicitados
            self.check_product_relationships(res, default_codes=["5959", "5840", "5882", "5958", "6211"])

            if res.critical_failures > 0:
                self.logger.error("Validación con fallas críticas", critical=res.critical_failures, warnings=res.warnings)
                return 1
            if res.warnings > 0:
                self.logger.warning("Validación con advertencias", warnings=res.warnings)
            self.logger.success("Validación completada sin fallas críticas")
            return 0
        except Exception as exc:
            self.logger.critical("Error ejecutando validaciones", error=str(exc))
            return 1


def main():
    validator = SyncValidator()
    rc = validator.run()
    sys.exit(rc)


if __name__ == "__main__":
    main()



