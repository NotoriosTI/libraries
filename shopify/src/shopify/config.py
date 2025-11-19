"""Inicialización centralizada de env-manager para la librería Shopify."""
from __future__ import annotations

import os
from typing import Any, Optional

try:
    from dev_utils import PrettyLogger
except ImportError:
    class PrettyLogger:
        def __init__(self, name: str) -> None:
            self.name = name
        def info(self, msg, **kwargs): print(f"[INFO][{self.name}] {msg} {kwargs}")
        def warning(self, msg, **kwargs): print(f"[WARN][{self.name}] {msg} {kwargs}")
        def error(self, msg, **kwargs): print(f"[ERROR][{self.name}] {msg} {kwargs}")

logger = PrettyLogger("shopify-config")

try:
    from env_manager import (
        init_config as _init_config,
        get_config as _env_get_config,
        require_config as _env_require_config,
    )
except ImportError:
    logger.warning("env-manager no disponible; se usarán variables de entorno sin validación.")
    _env_get_config = None
    _env_require_config = None
else:
    try:
        _init_config("config/config_vars.yaml")
        current_env = _env_require_config("ENVIRONMENT")
        logger.info("env-manager inicializado", environment=current_env)
    except Exception as exc:
        logger.error("Fallo al inicializar env-manager, usando os.environ como fallback", error=str(exc))
        _env_get_config = None
        _env_require_config = None

def get_config(key: str, default: Optional[Any] = None) -> Optional[Any]:
    if _env_get_config is None:
        return os.getenv(key, default)
    return _env_get_config(key, default)

def require_config(key: str) -> str:
    if _env_require_config is None:
        value = os.getenv(key)
        if value is None:
            raise RuntimeError(f"Missing configuration value: {key}")
        return value
    return _env_require_config(key)

__all__ = ["get_config", "require_config"]
