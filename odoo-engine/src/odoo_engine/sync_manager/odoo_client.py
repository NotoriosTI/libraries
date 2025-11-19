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
