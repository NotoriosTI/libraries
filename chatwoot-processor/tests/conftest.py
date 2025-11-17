from __future__ import annotations

import os
from pathlib import Path

from env_manager import init_config


_CONFIG_LOADED = False


def pytest_configure(config):  # noqa: D401
    """Initialise configuration for tests via env-manager."""

    global _CONFIG_LOADED
    if _CONFIG_LOADED:
        return

    env_file_exists = Path(".env").exists()

    if not env_file_exists:
        os.environ.setdefault("CHATWOOT_PROCESSOR_TOKEN", "test-token")
        os.environ.setdefault("CHATWOOT_PROCESSOR_ACCOUNT_ID", "12")
        os.environ.setdefault("CHATWOOT_PROCESSOR_PORT", "8000")
        os.environ.setdefault("CHATWOOT_BASE_URL", "https://app.chatwoot.com")

    init_config("config/config_vars.yaml")
    _CONFIG_LOADED = True
