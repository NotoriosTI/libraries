from datetime import datetime
from typing import Any, Dict, List, Optional

from .api import OdooAPI


class OdooSupply(OdooAPI):
    """
    Flujo de abastecimiento: maneja solicitudes de cotización (RFQ) y su
    conversión a Órdenes de Compra en Odoo.
    """

    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    # --------------------------- helpers --------------------------- #
    def _ensure_vendor(self, vendor_id: int) -> Dict[str, Any]:
        """Valida que el partner existe y está marcado como proveedor."""
        vendor_data = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.partner",
            "read",
            [[vendor_id]],
            {"fields": ["id", "name", "supplier_rank", "company_name"]},
        )
        if not vendor_data:
            raise ValueError(f"Proveedor con id {vendor_id} no existe")

        vendor = vendor_data[0]
        if vendor.get("supplier_rank", 0) <= 0:
            raise ValueError(
                f"El contacto '{vendor.get('name')}' no está marcado como proveedor (supplier_rank=0)"
            )
        return vendor

    def _fetch_products(self, product_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Obtiene datos mínimos de productos para armar líneas de compra."""
        if not product_ids:
            return {}
        products = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "product.product",
            "read",
            [list(set(product_ids))],
            {"fields": ["id", "name", "uom_po_id", "uom_id"]},
        )
        return {p["id"]: p for p in products}

    def _prepare_lines(
        self, order_lines: List[Dict[str, Any]]
    ) -> List[tuple]:
        """
        Normaliza líneas de RFQ a comandos Odoo [(0,0,{vals})].
        Requiere product_id; completa UoM y fecha si faltan.
        """
        if not order_lines:
            raise ValueError("Debe incluir al menos una línea de compra")

        product_ids = [
            line["product_id"] for line in order_lines if line.get("product_id")
        ]
        product_map = self._fetch_products(product_ids)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        prepared_lines = []
        for line in order_lines:
            product_id = line.get("product_id")
            if not product_id:
                raise ValueError("Cada línea necesita un product_id")

            product_data = product_map.get(product_id, {})
            uom = line.get("product_uom") or product_data.get("uom_po_id") or product_data.get("uom_id")
            if isinstance(uom, (list, tuple)):
                uom = uom[0]

            payload = {
                "product_id": product_id,
                "name": line.get("name") or product_data.get("name", ""),
                "product_qty": float(line.get("product_qty") or line.get("quantity") or 1),
                "price_unit": float(line.get("price_unit") or line.get("price") or 0),
                "date_planned": line.get("date_planned") or now_str,
            }

            if uom:
                payload["product_uom"] = uom

            if "taxes_id" in line:
                tax_ids = line.get("taxes_id") or []
                payload["taxes_id"] = [(6, 0, tax_ids)]

            prepared_lines.append((0, 0, payload))

        return prepared_lines

    # ----------------------------- RFQ ----------------------------- #
    def create_rfq(
        self,
        vendor_id: int,
        order_lines: List[Dict[str, Any]],
        rfq_values: Optional[Dict[str, Any]] = None,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Crea una nueva solicitud de cotización (purchase.order en borrador).

        Args:
            vendor_id: ID del proveedor (res.partner con supplier_rank > 0).
            order_lines: Lista de líneas {'product_id', 'product_qty', 'price_unit', ...}.
            rfq_values: Campos adicionales del modelo purchase.order.
            confirm: Si es True, confirma la RFQ a Orden de Compra.

        Returns:
            Dict con id, estado y nombre del proveedor.
        """
        vendor = self._ensure_vendor(vendor_id)
        values = {
            "partner_id": vendor_id,
            "order_line": self._prepare_lines(order_lines),
        }
        if rfq_values:
            values.update(rfq_values)

        order_id = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order",
            "create",
            [values],
        )

        final_state = "draft"
        if confirm:
            confirmed = self.confirm_rfq(order_id)
            final_state = confirmed.get("state", "purchase")

        return {
            "id": order_id,
            "state": final_state,
            "vendor": vendor.get("name"),
        }

    def confirm_rfq(self, order_id: int) -> Dict[str, Any]:
        """
        Confirma una RFQ existente y la convierte a Orden de Compra.
        """
        self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order",
            "button_confirm",
            [[order_id]],
        )
        order = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order",
            "read",
            [[order_id]],
            {"fields": ["id", "name", "state", "partner_id"]},
        )[0]
        return order

    def add_line_to_rfq(
        self, order_id: int, line: Dict[str, Any]
    ) -> int:
        """
        Añade una línea a un borrador de RFQ existente.
        Retorna el ID de la nueva línea.
        """
        payload = self._prepare_lines([line])[0][2]
        payload["order_id"] = order_id
        line_id = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order.line",
            "create",
            [payload],
        )
        return line_id

    def get_purchase_order(
        self, order_id: int, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Lee una RFQ/Orden de Compra con los campos solicitados."""
        fields = fields or [
            "name",
            "state",
            "partner_id",
            "order_line",
            "amount_total",
            "currency_id",
        ]
        record = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order",
            "read",
            [[order_id]],
            {"fields": fields},
        )
        return record[0] if record else {}

    def list_rfq(
        self,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retorna RFQs según dominio; por defecto solo borradores o enviadas.
        """
        fields = fields or ["name", "state", "partner_id", "date_order", "amount_total"]
        domain = domain or [("state", "in", ["draft", "sent"])]
        params: Dict[str, Any] = {"fields": fields, "order": "date_order desc"}
        if limit:
            params["limit"] = limit

        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "purchase.order",
            "search_read",
            [domain],
            params,
        )
