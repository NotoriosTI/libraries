from __future__ import annotations

from typing import Any

from env_manager import get_config as _get_config, init_config as _init_config


def get_config(key: str, default: Any | None = None) -> Any:
    """Proxy helper that delegates to the project-wide env-manager package."""

    return _get_config(key, default)


def init_config(config_path: str) -> None:
    """Initialise configuration using env-manager in a single place."""

    _init_config(config_path)


__all__ = ["get_config", "init_config"]
