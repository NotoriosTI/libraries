import logging
import os
import time
from urllib.parse import urlparse

import odoorpc
from config_manager import secrets


logger = logging.getLogger(__name__)


class OdooClient:
    """Wrapper de odoorpc con parseo robusto de URL, timeout y reintentos."""

    def __init__(self):
        self.url = (secrets.ODOO_PROD_URL or "").strip().rstrip("/")
        self.db = secrets.ODOO_PROD_DB
        self.username = secrets.ODOO_PROD_USERNAME
        self.password = secrets.ODOO_PROD_PASSWORD

        if not all([self.url, self.db, self.username, self.password]):
            raise ValueError("Faltan credenciales/URL de Odoo en variables de entorno")

        parsed = urlparse(self.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("ODOO_PROD_URL debe comenzar con http:// o https://")

        protocol = "jsonrpc+ssl" if parsed.scheme == "https" else "jsonrpc"
        # Puerto por defecto: 443 para https; 8069 para http (clásico de Odoo)
        default_port = 443 if parsed.scheme == "https" else 8069
        host = parsed.hostname or ""
        port = parsed.port or default_port
        if not host:
            raise ValueError("No se pudo parsear el host de ODOO_PROD_URL")

        # Timeout y reintentos configurables vía entorno (valores seguros por defecto)
        timeout = int(os.getenv("ODOO_TIMEOUT", "15"))
        retries = int(os.getenv("ODOO_CONNECT_RETRIES", "3"))

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                self.odoo = odoorpc.ODOO(
                    host,
                    port=port,
                    protocol=protocol,
                    timeout=timeout,
                )
                self.odoo.login(self.db, self.username, self.password)
                break
            except Exception as exc:  # conexión o login
                last_error = exc
                if attempt >= retries:
                    break
                # Backoff exponencial (máx 5s)
                time.sleep(min(2 ** (attempt - 1), 5))

        if last_error is not None:
            raise RuntimeError(
                f"No se pudo conectar a Odoo en {self.url} (host={host}, port={port}, protocol={protocol}) tras {retries} intento(s). Último error: {last_error}"
            )

    def search_read(
        self, model, domain=None, fields=None, limit=None, offset=0, order=None
    ):
        """Search and read records from Odoo."""
        domain = domain or []
        fields = fields or []
        return self.odoo.env[model].search_read(
            domain, fields=fields, offset=offset, limit=limit, order=order
        )

    def read(self, model, ids, fields=None):
        """Read records by ID."""
        return self.odoo.env[model].read(ids, fields=fields or [])

    def get_product_variant_attributes(self, product_ids: list) -> dict:
        """Obtiene atributos de variante para una lista de IDs de product.product.

        Implementación en batch usando odoorpc:
        1) Lee `product_template_attribute_value_ids` desde `product.product`
        2) Lee los nombres desde `product.template.attribute.value`

        Returns:
            dict: {product_id: ["100ml", "1L", ...]}

        Nota: Si ocurre un error, se loguea warning y se devuelve lo que se pudo.
        """
        if not product_ids:
            return {}

        # Evitar payloads enormes; 5000 es consistente con el batch size del SyncManager.
        chunk_size = 5000

        def _chunks(values, size):
            for i in range(0, len(values), size):
                yield values[i : i + size]

        # Stage 1: obtener ids de attribute values por producto
        products_by_id: dict[int, list[int]] = {}
        all_attr_ids: list[int] = []

        for chunk in _chunks([int(pid) for pid in product_ids if pid is not None], chunk_size):
            try:
                rows = self.read(
                    "product.product",
                    chunk,
                    fields=["id", "product_template_attribute_value_ids"],
                )
            except Exception as exc:
                logger.warning(
                    "No se pudieron leer variantes de product.product (chunk=%d): %s",
                    len(chunk),
                    exc,
                )
                continue

            for row in rows or []:
                pid = row.get("id")
                if pid is None:
                    continue
                attr_ids = row.get("product_template_attribute_value_ids") or []
                # Odoo puede devolver False en vez de lista
                if not isinstance(attr_ids, list):
                    attr_ids = []
                attr_ids = [int(aid) for aid in attr_ids if aid]
                products_by_id[int(pid)] = attr_ids
                all_attr_ids.extend(attr_ids)

        if not products_by_id:
            return {int(pid): [] for pid in product_ids if pid is not None}

        # Stage 2: resolver ids -> nombre
        attr_map: dict[int, str] = {}
        unique_attr_ids = list({int(aid) for aid in all_attr_ids if aid})
        if unique_attr_ids:
            for chunk in _chunks(unique_attr_ids, chunk_size):
                try:
                    attrs = self.read(
                        "product.template.attribute.value",
                        chunk,
                        fields=["id", "name"],
                    )
                except Exception as exc:
                    logger.warning(
                        "No se pudieron leer nombres de atributos (chunk=%d): %s",
                        len(chunk),
                        exc,
                    )
                    continue

                for a in attrs or []:
                    aid = a.get("id")
                    name = a.get("name")
                    if aid is None or not name:
                        continue
                    attr_map[int(aid)] = str(name)

        # Stage 3: construir resultado preservando orden de ids por producto
        result: dict[int, list[str]] = {}
        for pid, attr_ids in products_by_id.items():
            names: list[str] = []
            seen: set[str] = set()
            for aid in attr_ids:
                n = attr_map.get(int(aid))
                if not n:
                    continue
                # dedupe conservando orden
                if n in seen:
                    continue
                seen.add(n)
                names.append(n)
            result[int(pid)] = names

        # Asegurar que devolvemos key para todos los IDs solicitados
        for pid in product_ids:
            if pid is None:
                continue
            result.setdefault(int(pid), [])

        return result

    def create_purchase_order(self, product_id, supplier_id, quantity, unit_price, product_name=""):
        """
        Create a purchase order in Odoo using the existing OdooClient

        Args:
            product_id (int): Odoo product ID
            supplier_id (int): Odoo supplier/partner ID
            quantity (float): Quantity to order
            unit_price (float): Unit price for the product
            product_name (str): Product name for logging

        Returns:
            int: Purchase order ID if successful, None otherwise
        """
        try:
            # Prepare purchase order data
            purchase_order_data = {
                'partner_id': supplier_id,
                'order_line': [
                    (0, 0, {
                        'product_id': product_id,
                        'product_qty': quantity,
                        'price_unit': unit_price,
                        'name': product_name or f'Purchase for product {product_id}'
                    }),
                ],
            }

            # Create the purchase order
            PurchaseOrder = self.odoo.env['purchase.order']
            new_po_id = PurchaseOrder.create(purchase_order_data)

            # Confirm the purchase order
            new_po = PurchaseOrder.browse(new_po_id)
            new_po.button_confirm()

            print(f"✅ Purchase Order {new_po_id} created and confirmed successfully!")
            print(f"   Product: {product_name} (ID: {product_id})")
            print(f"   Supplier ID: {supplier_id}")
            print(f"   Quantity: {quantity}")
            print(f"   Unit Price: {unit_price}")

            return new_po_id

        except ImportError:
            print("❌ OdooClient not available. Make sure odoo_engine.utils is installed")
            return None
        except Exception as e:
            print(f"❌ Error creating purchase order: {str(e)}")
            return None

    def create_purchase_order_bulk(self, supplier_id, lines):
        """Create a single purchase order with multiple lines for one supplier.

        Args:
            supplier_id (int): Partner ID
            lines (list[dict]): Each dict must contain product_id, product_qty, price_unit, name

        Returns:
            int | None: Purchase order ID
        """
        try:
            order_line_payload = []
            for line in lines:
                order_line_payload.append(
                    (0, 0, {
                        'product_id': int(line['product_id']),
                        'product_qty': float(line['product_qty']),
                        'price_unit': float(line['price_unit']),
                        'name': line.get('name') or f"Purchase for product {line['product_id']}"
                    })
                )

            purchase_order_data = {
                'partner_id': int(supplier_id),
                'order_line': order_line_payload,
            }

            PurchaseOrder = self.odoo.env['purchase.order']
            new_po_id = PurchaseOrder.create(purchase_order_data)

            new_po = PurchaseOrder.browse(new_po_id)
            new_po.button_confirm()

            print(f"✅ Purchase Order {new_po_id} (bulk) created and confirmed successfully!")
            print(f"   Supplier ID: {supplier_id}")
            print(f"   Lines: {len(lines)}")
            return new_po_id
        except Exception as e:
            print(f"❌ Error creating bulk purchase order: {str(e)}")
            return None
    
