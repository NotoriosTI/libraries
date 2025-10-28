from __future__ import annotations

from pathlib import Path

import pytest

from env_manager import ConfigManager


def _write_yaml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_required_variable_missing_raises(tmp_path):
    config = tmp_path / "config.yaml"
    _write_yaml(
        config,
        """
variables:
  API_KEY:
    source: API_KEY
validation:
  required:
    - API_KEY
        """.strip(),
    )

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        ConfigManager(
            str(config),
            secret_origin="local",
            dotenv_path=str(env_file),
        )

    assert "Required variable 'API_KEY' not found" in str(exc.value)


def test_defaults_are_used_when_missing(tmp_path):
    config = tmp_path / "config.yaml"
    _write_yaml(
        config,
        """
variables:
  WORKERS:
    source: WORKERS
    type: int
    default: 4
validation:
  optional:
    - WORKERS
        """.strip(),
    )

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    manager = ConfigManager(
        str(config),
        secret_origin="local",
        dotenv_path=str(env_file),
    )

    assert manager.get("WORKERS") == 4


def test_strict_override_disables_strict(tmp_path):
    config = tmp_path / "config.yaml"
    _write_yaml(
        config,
        """
variables:
  OPTIONAL:
    source: OPTIONAL
validation:
  strict: true
        """.strip(),
    )

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    manager = ConfigManager(
        str(config),
        secret_origin="local",
        dotenv_path=str(env_file),
        strict=False,
    )

    assert manager.get("OPTIONAL") is None
