import os
import time
from urllib.parse import urlparse

import odoorpc
from env_manager import init_config, get_config, require_config

init_config(
    "config/config_vars.yaml",
    secret_origin=None,
    gcp_project_id=None,
    strict=None,
    dotenv_path=None,
    debug=False,
)

class OdooClient:
    """Wrapper de odoorpc con parseo robusto de URL, timeout y reintentos."""

    def __init__(self):
        self.url = (get_config("ODOO_PROD_URL") or "").strip().rstrip("/")
        self.db = get_config("ODOO_PROD_DB")
        self.username = get_config("ODOO_PROD_USERNAME")
        self.password = get_config("ODOO_PROD_PASSWORD")

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
    
