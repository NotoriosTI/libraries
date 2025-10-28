from __future__ import annotations

import os
from pathlib import Path

import pytest

import env_manager.manager as manager_module
from env_manager import ConfigManager, get_config, init_config, require_config

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def prod_config(tmp_path: Path) -> Path:
    config_source = FIXTURES / "prod_config.yaml"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_source.read_text(), encoding="utf-8")
    return config_path


@pytest.mark.integration
def test_production_like_flow(prod_config: Path):
    manager_module._SINGLETON = None  # ensure clean singleton state

    if not os.getenv("RUN_REAL_GCP_TESTS"):
        pytest.skip("Set RUN_REAL_GCP_TESTS=1 to run GCP integration test.")

    gcp_manager = ConfigManager(
        str(prod_config),
        secret_origin="gcp",
        gcp_project_id="notorios",
    )

    required_keys = {
        "ODOO_PROD_URL",
        "OPENAI_API_KEY",
        "JUAN_ANTHROPIC_API_KEY",
        "SLACK_BOT_TOKEN",
    }

    for key in required_keys:
        value = gcp_manager.require(key)
        assert isinstance(value, str) and value
        assert os.environ[key] == value

    manager_module._SINGLETON = None
    init_config(
        str(prod_config),
        secret_origin="gcp",
        gcp_project_id="notorios",
    )
    for key in required_keys:
        value = require_config(key)
        assert isinstance(value, str) and value

    for key in required_keys:
        os.environ.pop(key, None)

    manager_module._SINGLETON = None
    env_file = prod_config.parent / ".env"
    env_values = {
        "ODOO_PROD_URL": "https://odoo.local",
        "OPENAI_API_KEY": "sk-test-openai",
        "JUAN_ANTHROPIC_API_KEY": "anthropic-test-key",
        "SLACK_BOT_TOKEN": "xoxb-test-token",
    }
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in env_values.items()),
        encoding="utf-8",
    )

    local_manager = ConfigManager(
        str(prod_config),
        secret_origin="local",
        dotenv_path=str(env_file),
    )

    for key, expected in env_values.items():
        assert local_manager.require(key) == expected
        assert os.environ[key] == expected

    manager_module._SINGLETON = None
    init_config(
        str(prod_config),
        secret_origin="local",
        dotenv_path=str(env_file),
    )

    for key, expected in env_values.items():
        assert get_config(key) == expected

    manager_module._SINGLETON = None