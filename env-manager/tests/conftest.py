"""Test configuration for env-manager."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests start with a clean slate for key env variables."""

    for key in (
        "DB_PASSWORD",
        "PORT",
        "DEBUG_MODE",
        "TIMEOUT",
        "GCP_PROJECT_ID",
        "SECRET_ORIGIN",
        "API_KEY",
        "OPTIONAL",
        "WORKERS",
    ):
        monkeypatch.delenv(key, raising=False)
