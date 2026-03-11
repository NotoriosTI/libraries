"""Unit tests for EnvironmentConfig and parse_environments."""

from __future__ import annotations

import pytest

from env_manager.environment import EnvironmentConfig, parse_environments


# ---------------------------------------------------------------------------
# is_default field defaults
# ---------------------------------------------------------------------------


def test_default_field_absent_is_false():
    """When the 'default' key is absent, is_default must be False."""
    raw = {
        "environments": {
            "staging": {"origin": "local"},
        }
    }
    envs = parse_environments(raw)
    assert envs["staging"].is_default is False


def test_default_true_sets_is_default():
    """When 'default: true' is present, is_default must be True."""
    raw = {
        "environments": {
            "staging": {"origin": "local", "default": True},
        }
    }
    envs = parse_environments(raw)
    assert envs["staging"].is_default is True


def test_default_false_explicit():
    """Explicitly setting 'default: false' keeps is_default as False."""
    raw = {
        "environments": {
            "staging": {"origin": "local", "default": False},
        }
    }
    envs = parse_environments(raw)
    assert envs["staging"].is_default is False


# ---------------------------------------------------------------------------
# Multiple default: true validation
# ---------------------------------------------------------------------------


def test_multiple_default_true_raises():
    """Two or more environments with default: true must raise ValueError."""
    raw = {
        "environments": {
            "alpha": {"origin": "local", "default": True},
            "beta": {"origin": "local", "default": True},
        }
    }
    with pytest.raises(ValueError, match="default: true") as exc_info:
        parse_environments(raw)
    # Both names should appear in the error message
    assert "alpha" in str(exc_info.value)
    assert "beta" in str(exc_info.value)


def test_single_default_true_is_valid():
    """Exactly one environment with default: true parses without error."""
    raw = {
        "environments": {
            "alpha": {"origin": "local", "default": True},
            "beta": {"origin": "local"},
        }
    }
    envs = parse_environments(raw)  # must not raise
    assert envs["alpha"].is_default is True
    assert envs["beta"].is_default is False


# ---------------------------------------------------------------------------
# Existing field behaviour (regression)
# ---------------------------------------------------------------------------


def test_no_environments_key_returns_empty():
    envs = parse_environments({})
    assert envs == {}


def test_origin_required():
    raw = {"environments": {"dev": {"dotenv_path": ".env"}}}
    with pytest.raises(ValueError, match="origin"):
        parse_environments(raw)


def test_invalid_origin_raises():
    raw = {"environments": {"dev": {"origin": "s3"}}}
    with pytest.raises(ValueError, match="invalid origin"):
        parse_environments(raw)


def test_local_default_dotenv_path():
    raw = {"environments": {"dev": {"origin": "local"}}}
    envs = parse_environments(raw)
    assert envs["dev"].dotenv_path == ".env"


def test_local_explicit_dotenv_path():
    raw = {"environments": {"dev": {"origin": "local", "dotenv_path": ".env.staging"}}}
    envs = parse_environments(raw)
    assert envs["dev"].dotenv_path == ".env.staging"


def test_gcp_requires_project_id():
    raw = {"environments": {"prod": {"origin": "gcp"}}}
    with pytest.raises(ValueError, match="gcp_project_id"):
        parse_environments(raw)


def test_gcp_sets_project_id_and_clears_dotenv():
    raw = {
        "environments": {
            "prod": {
                "origin": "gcp",
                "gcp_project_id": "my-project",
                "dotenv_path": "should-be-ignored",
            }
        }
    }
    envs = parse_environments(raw)
    assert envs["prod"].gcp_project_id == "my-project"
    assert envs["prod"].dotenv_path is None


def test_multiple_environments_parse_independently():
    raw = {
        "environments": {
            "default": {"origin": "local"},
            "staging": {"origin": "local", "dotenv_path": ".env.staging"},
            "production": {"origin": "gcp", "gcp_project_id": "prod-project"},
        }
    }
    envs = parse_environments(raw)
    assert set(envs) == {"default", "staging", "production"}
    assert envs["default"].origin == "local"
    assert envs["staging"].dotenv_path == ".env.staging"
    assert envs["production"].gcp_project_id == "prod-project"
