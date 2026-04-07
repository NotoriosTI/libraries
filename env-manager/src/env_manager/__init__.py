"""env-manager package initialization."""

import warnings

warnings.warn(
    "env_manager from NotoriosTI/libraries is deprecated. "
    "Install the replacement: pip install env-manager @ git+https://github.com/NotoriosTI/env-manager.git",
    DeprecationWarning,
    stacklevel=2,
)

from .manager import ConfigManager, get_config, init_config, require_config
from .base import SecretLoader
from .factory import create_loader

__all__ = [
    "ConfigManager",
    "get_config",
    "init_config",
    "require_config",
    "SecretLoader",
    "create_loader",
]

__version__ = "0.1.5"
