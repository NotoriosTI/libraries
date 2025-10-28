"""Loader implementation for local .env files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, find_dotenv, load_dotenv

from env_manager.base import SecretLoader

try:
    from dev_utils.pretty_logger import PrettyLogger
except ImportError:  # pragma: no cover
    from env_manager.utils import PrettyLogger


logger = PrettyLogger("env-manager")


class DotEnvLoader(SecretLoader):
    """Load secrets from a .env file and the current environment."""

    def __init__(self, dotenv_path: Optional[str] = None) -> None:
        self._dotenv_path = self._resolve_path(dotenv_path)
        self._values = self._load_dotenv_values()

    def _resolve_path(self, dotenv_path: Optional[str]) -> Optional[str]:
        if dotenv_path:
            return str(Path(dotenv_path).expanduser().resolve())
        discovered = find_dotenv(usecwd=True)
        if discovered:
            return discovered
        candidate = Path.cwd() / ".env"
        return str(candidate) if candidate.exists() else None

    def _load_dotenv_values(self) -> dict[str, str]:
        if not self._dotenv_path:
            return {}
        load_dotenv(self._dotenv_path, override=False)
        values = dotenv_values(self._dotenv_path)
        return {key: value for key, value in values.items() if value is not None}

    def get(self, key: str) -> Optional[str]:
        return os.environ.get(key, self._values.get(key))

    def get_many(self, keys: list[str]) -> dict[str, Optional[str]]:
        return {key: self.get(key) for key in keys}

    @property
    def dotenv_path(self) -> Optional[str]:
        """Return the resolved path to the .env file, if any."""

        return self._dotenv_path
