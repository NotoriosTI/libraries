import odoorpc
from config_manager import secrets


class OdooClient:
    """Wrapper around odoorpc for simpler Odoo access."""

    def __init__(self):
        self.url = secrets.ODOO_PROD_URL
        self.db = secrets.ODOO_PROD_DB
        self.username = secrets.ODOO_PROD_USERNAME
        self.password = secrets.ODOO_PROD_PASSWORD

        # Parse host/port from URL (odoorpc needs host + port separately)
        if self.url.startswith("http://"):
            host_port = self.url.replace("http://", "").split(":")
            protocol = "jsonrpc"
        elif self.url.startswith("https://"):
            host_port = self.url.replace("https://", "").split(":")
            protocol = "jsonrpc+ssl"
        else:
            raise ValueError("ODOO_URL must start with http:// or https://")

        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 8069

        self.odoo = odoorpc.ODOO(host, port=port, protocol=protocol)
        self.odoo.login(self.db, self.username, self.password)

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
