"""env-manager adapter so tests/scripts can read Odoo credentials consistently."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config_vars.yaml"

try:
    from env_manager import (
        init_config as _init_config,
        get_config as _env_get_config,
    )
    _init_config(str(CONFIG_PATH))
except Exception as exc:  # env-manager ausente o problema de init
    print(f"⚠️  No se pudo inicializar env-manager ({exc}); usando os.environ como respaldo.")
    _env_get_config = None


def _read_value(key: str, default: Any = None) -> Any:
    if _env_get_config is not None:
        try:
            value = _env_get_config(key)
        except RuntimeError:
            value = None
        if value is not None:
            return value
    return os.getenv(key, default)


class OdooSettings:
    """Expose Odoo credentials via env-manager (or environment fallback)."""

    def get_odoo_config(self, *, use_test: bool = False) -> Dict[str, str]:
        prefix = "ODOO_TEST_" if use_test else "ODOO_PROD_"
        return {
            "url": self._require(prefix + "URL"),
            "db": self._require(prefix + "DB"),
            "username": self._require(prefix + "USERNAME"),
            "password": self._require(prefix + "PASSWORD"),
        }

    def _require(self, key: str) -> str:
        value = _read_value(key)
        if not value:
            raise RuntimeError(f"Missing configuration value: {key}")
        return value

    def __getattr__(self, name: str) -> Any:
        value = _read_value(name)
        if value is None:
            raise AttributeError(name)
        return value


secrets = OdooSettings()
Settings = OdooSettings
__all__ = ["OdooSettings", "secrets", "Settings"]
