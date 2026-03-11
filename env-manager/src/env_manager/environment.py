"""EnvironmentConfig dataclass and parser for named environments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class EnvironmentConfig:
    """Parsed representation of a single named environment."""

    name: str
    origin: str
    dotenv_path: Optional[str] = None
    gcp_project_id: Optional[str] = None
    is_default: bool = False


def parse_environments(
    raw_config: dict[str, Any],
    project_root: Optional[str] = None,
) -> dict[str, EnvironmentConfig]:
    """Parse the ``environments:`` section from a raw YAML config dict.

    Returns an empty dict when the key is absent.
    Raises ``ValueError`` for any schema violation, including more than one
    environment setting ``default: true``.
    """
    raw_envs = raw_config.get("environments")
    if raw_envs is None:
        return {}

    if not isinstance(raw_envs, dict):
        raise ValueError(
            "'environments' section in config must be a mapping of environment definitions."
        )

    result: dict[str, EnvironmentConfig] = {}

    for env_name, env_data in raw_envs.items():
        if not isinstance(env_data, dict):
            raise ValueError(
                f"Environment '{env_name}' must be a mapping, "
                f"got {type(env_data).__name__}."
            )

        origin = env_data.get("origin")
        if origin is None:
            raise ValueError(
                f"Environment '{env_name}' is missing required field 'origin'."
            )
        origin = str(origin).strip().lower()
        if origin not in ("local", "gcp"):
            raise ValueError(
                f"Environment '{env_name}' has invalid origin '{origin}'. "
                "Must be 'local' or 'gcp'."
            )

        if origin == "local":
            dotenv_path: Optional[str] = env_data.get("dotenv_path", ".env")
            gcp_project_id: Optional[str] = None
        else:  # gcp
            gcp_project_id = env_data.get("gcp_project_id")
            if not gcp_project_id:
                raise ValueError(
                    f"Environment '{env_name}' with origin 'gcp' requires 'gcp_project_id'."
                )
            dotenv_path = None

        is_default = bool(env_data.get("default", False))

        result[env_name] = EnvironmentConfig(
            name=env_name,
            origin=origin,
            dotenv_path=dotenv_path,
            gcp_project_id=gcp_project_id,
            is_default=is_default,
        )

    # At most one environment may declare default: true
    explicit_defaults = [name for name, cfg in result.items() if cfg.is_default]
    if len(explicit_defaults) > 1:
        raise ValueError(
            f"Only one environment may set 'default: true', "
            f"but found multiple: {explicit_defaults}"
        )

    return result
