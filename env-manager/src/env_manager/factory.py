"""Factory helpers for building secret loaders."""

from __future__ import annotations

from typing import Optional

from env_manager.base import SecretLoader
from env_manager.loaders import DotEnvLoader, GCPSecretLoader

try:
    from dev_utils.pretty_logger import PrettyLogger
except ImportError:  # pragma: no cover
    from env_manager.utils import PrettyLogger


logger = PrettyLogger("env-manager")


def create_loader(
    secret_origin: str,
    *,
    gcp_project_id: Optional[str] = None,
    dotenv_path: Optional[str] = None,
) -> SecretLoader:
    """Instantiate the appropriate loader for ``secret_origin``."""

    origin = (secret_origin or "local").strip().lower()

    if origin == "local":
        logger.info("Loading secrets from .env")
        return DotEnvLoader(dotenv_path=dotenv_path)

    if origin == "gcp":
        if not gcp_project_id:
            raise ValueError(
                "GCP project ID must be provided when SECRET_ORIGIN is 'gcp'."
            )
        logger.info("Loading secrets from GCP Secret Manager")
        return GCPSecretLoader(project_id=gcp_project_id)

    raise ValueError(
        f"Unsupported SECRET_ORIGIN '{secret_origin}'. Expected 'local' or 'gcp'."
    )
