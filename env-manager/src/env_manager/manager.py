"""High-level configuration manager for secrets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import dotenv_values, find_dotenv

from env_manager.factory import create_loader
from env_manager.utils import coerce_type, load_yaml, logger, mask_secret

from .base import SecretLoader


class ConfigManager:
    """Load and validate configuration variables from multiple sources."""

    def __init__(
        self,
        config_path: str,
        *,
        secret_origin: Optional[str] = None,
        gcp_project_id: Optional[str] = None,
        strict: Optional[bool] = None,
        auto_load: bool = True,
        dotenv_path: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        self._config_path = Path(config_path).expanduser().resolve()
        self._raw_config = load_yaml(str(self._config_path))
        self._variables = self._extract_variables()
        self._validation = self._extract_validation()
        self._dotenv_path = self._resolve_dotenv_path(dotenv_path)
        self._dotenv_values = self._read_dotenv_values()
        self._debug = debug

        self.secret_origin = self._resolve_secret_origin(secret_origin)
        self.gcp_project_id = self._resolve_gcp_project_id(gcp_project_id)
        self.strict = self._resolve_strict(strict)

        self._loader: Optional[SecretLoader] = None
        self._values: dict[str, Any] = {}
        self._loaded = False

        if auto_load:
            self.load()

    def _resolve_dotenv_path(self, provided: Optional[str]) -> Optional[str]:
        if provided:
            candidate = Path(provided).expanduser()
            return str(candidate.resolve()) if candidate.exists() else None
        discovered = find_dotenv(usecwd=True)
        if discovered:
            return discovered
        fallback = self._config_path.parent / ".env"
        return str(fallback) if fallback.exists() else None

    def _read_dotenv_values(self) -> dict[str, str]:
        if not self._dotenv_path:
            return {}
        values = dotenv_values(self._dotenv_path)
        return {key: value for key, value in values.items() if value is not None}

    def _resolve_secret_origin(self, provided: Optional[str]) -> str:
        # Priority order:
        # 1. Explicitly provided parameter
        # 2. Environment variable
        # 3. Value from .env file (read without loading entire file)
        # 4. Default: "local"
        if provided:
            return provided.strip().lower()
        
        # Check os.environ first
        env_origin = os.environ.get("SECRET_ORIGIN")
        if env_origin:
            return env_origin.strip().lower()
        
        # Check .env file without loading entire file to os.environ
        if self._dotenv_values:
            dotenv_origin = self._dotenv_values.get("SECRET_ORIGIN")
            if dotenv_origin:
                return dotenv_origin.strip().lower()
        
        return "local"

    def _resolve_gcp_project_id(self, provided: Optional[str]) -> Optional[str]:
        # Priority order:
        # 1. Explicitly provided parameter
        # 2. Environment variable
        # 3. Value from .env file
        # 4. Not set
        candidate = (
            provided
            or os.environ.get("GCP_PROJECT_ID")
            or self._dotenv_values.get("GCP_PROJECT_ID")
        )
        if candidate:
            os.environ.setdefault("GCP_PROJECT_ID", candidate)
            return candidate
        logger.warning("GCP_PROJECT_ID not set. Some features may not work.")
        return None

    def _resolve_strict(self, provided: Optional[bool]) -> bool:
        if provided is not None:
            return provided
        return bool(self._validation.get("strict", False))

    def _extract_variables(self) -> dict[str, dict[str, Any]]:
        variables = self._raw_config.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError(
                "'variables' section in config must be a mapping of variable definitions."
            )
        return variables

    def _extract_validation(self) -> dict[str, Any]:
        validation = self._raw_config.get("validation", {})
        if validation and not isinstance(validation, dict):
            raise ValueError("'validation' section must be a mapping if provided.")
        data = validation or {}
        for key in ("required", "optional"):
            collection = data.get(key)
            if collection is None:
                continue
            if not isinstance(collection, list):
                raise ValueError(
                    f"Validation '{key}' entry must be a list if provided."
                )
        return data

    def _ensure_loader(self) -> SecretLoader:
        if self._loader is None:
            self._loader = create_loader(
                self.secret_origin,
                gcp_project_id=self.gcp_project_id,
                dotenv_path=self._dotenv_path,
            )
        return self._loader

    def load(self) -> None:
        """Load variables according to the YAML configuration."""

        if self._loaded:
            return

        loader = self._ensure_loader()

        sources = {
            name: self._validate_variable_definition(name, definition)
            for name, definition in self._variables.items()
        }

        fetched = loader.get_many(list(sources.values()))

        required = set(self._validation.get("required", []) or [])
        optional = set(self._validation.get("optional", []) or [])

        for var_name, source in sources.items():
            definition = self._variables[var_name]
            target_type = str(definition.get("type", "str"))
            has_default = "default" in definition
            default_value = definition.get("default") if has_default else None
            raw_value = fetched.get(source)
            missing_value = raw_value is None

            if missing_value:
                message = (
                    f"Variable '{var_name}' not found in source '{source}' "
                    f"using origin '{self.secret_origin}'."
                )
                if self.strict:
                    logger.error(message)
                    raise RuntimeError(message)
                if var_name in required:
                    logger.error(
                        f"Required variable {var_name} not found"
                    )
                    origin_context = (
                        "GCP Secret Manager project '%s'"
                        % (self.gcp_project_id or "unknown-project")
                        if self.secret_origin == "gcp"
                        else ".env file or environment"
                    )
                    raise RuntimeError(
                        "Required variable '%s' not found in %s. "
                        "Ensure the secret exists and the service has access."
                        % (var_name, origin_context)
                    )
                if var_name in optional:
                    logger.warning(
                        f"Optional variable {var_name} not found"
                    )

                if has_default:
                    raw_value = default_value
                else:
                    self._values[var_name] = None
                    continue

            try:
                coerced_value = coerce_type(raw_value, target_type, var_name)
            except ValueError as exc:
                logger.error(
                    f"Type coercion failed for {var_name}: {exc}"
                )
                raise
            self._values[var_name] = coerced_value
            os.environ[var_name] = str(coerced_value)
            display_value = (
                str(coerced_value)
                if self._debug
                else mask_secret(str(coerced_value))
            )
            logger.info(f"Loaded {var_name}: {display_value}")

        self._loaded = True

    def _validate_variable_definition(
        self, name: str, definition: Any
    ) -> str:
        if not isinstance(definition, dict):
            raise ValueError(
                f"Invalid configuration for '{name}'. Expected a mapping."
            )
        source = definition.get("source")
        if not source or not isinstance(source, str):
            raise ValueError(
                f"Variable '{name}' must define a string 'source' entry."
            )
        v_type = str(definition.get("type", "str"))
        if v_type not in {"str", "int", "float", "bool"}:
            raise ValueError(
                f"Variable '{name}' uses unsupported type '{v_type}'."
            )
        return source

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for ``key`` if present, else ``default``."""

        if not self._loaded:
            self.load()
        return self._values.get(key, default)

    def require(self, key: str) -> Any:
        """Return the value for ``key`` or raise if missing."""

        if not self._loaded:
            self.load()
        if key not in self._values or self._values[key] is None:
            raise RuntimeError(
                f"Required configuration '{key}' is missing. "
                "Call init_config or set a default."
            )
        return self._values[key]

    @property
    def values(self) -> dict[str, Any]:
        """Return a copy of loaded values."""

        if not self._loaded:
            self.load()
        return dict(self._values)


_SINGLETON: Optional[ConfigManager] = None


def init_config(
    config_path: str,
    *,
    secret_origin: Optional[str] = None,
    gcp_project_id: Optional[str] = None,
    strict: Optional[bool] = None,
    auto_load: bool = True,
    dotenv_path: Optional[str] = None,
    debug: bool = False,
) -> ConfigManager:
    """Initialise the global configuration manager singleton."""

    global _SINGLETON
    if _SINGLETON is not None:
        logger.warning(
            "Configuration manager already initialised. Replacing existing instance."
        )
    _SINGLETON = ConfigManager(
        config_path,
        secret_origin=secret_origin,
        gcp_project_id=gcp_project_id,
        strict=strict,
        auto_load=auto_load,
        dotenv_path=dotenv_path,
        debug=debug,
    )
    return _SINGLETON


def get_config(key: str, default: Any = None) -> Any:
    """Retrieve a configuration value from the singleton manager."""

    if _SINGLETON is None:
        raise RuntimeError("Configuration manager not initialised. Call init_config().")
    return _SINGLETON.get(key, default)


def require_config(key: str) -> Any:
    """Retrieve a mandatory configuration value.

    Raises an error if the configuration manager is not initialised or the value is
    missing.
    """

    if _SINGLETON is None:
        raise RuntimeError("Configuration manager not initialised. Call init_config().")
    return _SINGLETON.require(key)
