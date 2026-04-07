"""
Centralized configuration and secret management for all services.
"""

import warnings

warnings.warn(
    "config_manager from NotoriosTI/libraries is deprecated. "
    "Install the replacement: pip install env-manager @ git+https://github.com/NotoriosTI/env-manager.git",
    DeprecationWarning,
    stacklevel=2,
)

from config_manager.settings import secrets
from config_manager import juan, emma, emilia, common

__all__ = [
    "juan",
    "emma",
    "emilia",
    "common",
    "secrets",
]
