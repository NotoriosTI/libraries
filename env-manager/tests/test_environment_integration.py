"""Integration tests: active_environment selection via ConfigManager."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import env_manager.manager as manager_module
from env_manager import ConfigManager


@pytest.fixture(autouse=True)
def reset_singleton():
    manager_module._SINGLETON = None  # type: ignore[attr-defined]
    yield
    manager_module._SINGLETON = None  # type: ignore[attr-defined]


def _make_config(tmp_path: Path, yaml_body: str) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_body, encoding="utf-8")
    return config_path


def test_explicit_default_true_wins_over_named_default_key(tmp_path, monkeypatch):
    """When key 'default' (no flag) and 'gcp' (default: true) coexist and
    ENVIRONMENT is unset, the active environment must be 'gcp'."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    yaml_body = """
variables:
  DUMMY:
    default: placeholder

environments:
  default:
    origin: local
    dotenv_path: .env.default
  gcp:
    origin: local
    dotenv_path: .env.gcp
    default: true
"""
    config_path = _make_config(tmp_path, yaml_body)

    mgr = ConfigManager(str(config_path), secret_origin="local", auto_load=False)
    active = mgr.active_environment

    assert active is not None
    assert active.name == "gcp"


def test_named_default_key_selected_when_no_flag(tmp_path, monkeypatch):
    """When no environment has default: true, the key named 'default' is selected."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    yaml_body = """
variables:
  DUMMY:
    default: placeholder

environments:
  default:
    origin: local
    dotenv_path: .env.default
  staging:
    origin: local
    dotenv_path: .env.staging
"""
    config_path = _make_config(tmp_path, yaml_body)

    mgr = ConfigManager(str(config_path), secret_origin="local", auto_load=False)
    active = mgr.active_environment

    assert active is not None
    assert active.name == "default"


def test_environment_env_var_takes_precedence(tmp_path, monkeypatch):
    """ENVIRONMENT env var always wins, even over default: true."""
    monkeypatch.setenv("ENVIRONMENT", "staging")

    yaml_body = """
variables:
  DUMMY:
    default: placeholder

environments:
  staging:
    origin: local
    dotenv_path: .env.staging
  production:
    origin: local
    dotenv_path: .env.production
    default: true
"""
    config_path = _make_config(tmp_path, yaml_body)

    mgr = ConfigManager(str(config_path), secret_origin="local", auto_load=False)
    active = mgr.active_environment

    assert active is not None
    assert active.name == "staging"


def test_no_environments_active_is_none(tmp_path, monkeypatch):
    """When the config has no environments section, active_environment is None."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    yaml_body = """
variables:
  DUMMY:
    default: placeholder
"""
    config_path = _make_config(tmp_path, yaml_body)

    mgr = ConfigManager(str(config_path), secret_origin="local", auto_load=False)
    assert mgr.active_environment is None
