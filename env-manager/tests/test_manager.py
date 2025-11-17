from __future__ import annotations

import os
from pathlib import Path

import pytest

import env_manager.manager as manager_module
from env_manager import ConfigManager, get_config, init_config, require_config

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def reset_singleton():
    manager_module._SINGLETON = None  # type: ignore[attr-defined]
    yield
    manager_module._SINGLETON = None  # type: ignore[attr-defined]


def _prepare_config(tmp_path: Path) -> tuple[Path, Path]:
    config_source = FIXTURES / "test_config.yaml"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_source.read_text(), encoding="utf-8")
    env_path = tmp_path / ".env"
    return config_path, env_path


def test_config_manager_local_loading(tmp_path):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text(
        "\n".join(
            [
                "DB_PASSWORD=password123",
                "PORT=9000",
                "DEBUG_MODE=true",
                "TIMEOUT=2.75",
                "GCP_PROJECT_ID=test-project",
            ]
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
    )

    assert manager.get("DB_PASSWORD") == "password123"
    assert manager.require("DB_PASSWORD") == "password123"
    assert manager.get("PORT") == 9000
    assert manager.get("DEBUG_MODE") is True
    assert manager.get("TIMEOUT") == 2.75
    assert os.environ["DB_PASSWORD"] == "password123"
    assert os.environ["GCP_PROJECT_ID"] == "test-project"


def test_missing_required_variable_raises(tmp_path):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text("PORT=9000\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        ConfigManager(
            str(config_path),
            secret_origin="local",
            dotenv_path=str(env_path),
        )
    assert "Required variable 'DB_PASSWORD' not found" in str(exc.value)


def test_optional_variable_warns(tmp_path, capsys):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text("DB_PASSWORD=password123\n", encoding="utf-8")

    manager = ConfigManager(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
    )

    output = capsys.readouterr().out
    assert "Optional variable DEBUG_MODE not found" in output
    assert manager.get("DEBUG_MODE") is False


def test_strict_mode_raises_on_missing(tmp_path):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        ConfigManager(
            str(config_path),
            secret_origin="local",
            dotenv_path=str(env_path),
            strict=True,
        )
    assert "Variable 'DB_PASSWORD' not found" in str(exc.value)


def test_singleton_api(tmp_path):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text("DB_PASSWORD=password123\n", encoding="utf-8")

    init_config(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
    )

    assert get_config("DB_PASSWORD") == "password123"
    assert require_config("DEBUG_MODE") is False


def test_reinit_logs_warning(tmp_path, capsys):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text("DB_PASSWORD=password123\n", encoding="utf-8")

    init_config(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
    )
    capsys.readouterr()
    init_config(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
    )

    output = capsys.readouterr().out
    assert "Configuration manager already initialised" in output


def test_debug_parameter_disables_masking(tmp_path, capsys):
    config_path, env_path = _prepare_config(tmp_path)
    env_path.write_text(
        "\n".join(
            [
                "DB_PASSWORD=password123",
                "PORT=1234",
                "DEBUG_MODE=true",
                "TIMEOUT=3.14",
            ]
        ),
        encoding="utf-8",
    )

    ConfigManager(
        str(config_path),
        secret_origin="local",
        dotenv_path=str(env_path),
        debug=True,
    )

    output = capsys.readouterr().out
    assert "Loaded DB_PASSWORD: password123" in output
