"""Loader implementation backed by Google Secret Manager."""

from __future__ import annotations

from typing import Optional

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager

from env_manager.base import SecretLoader

try:
    from dev_utils.pretty_logger import PrettyLogger
except ImportError:  # pragma: no cover
    from env_manager.utils import PrettyLogger


logger = PrettyLogger("env-manager")


class GCPSecretLoader(SecretLoader):
    """Load secrets from GCP Secret Manager with simple caching."""

    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise ValueError(
                "GCP project ID is required when using the GCP secret loader."
            )
        self._project_id = project_id
        self._client = secretmanager.SecretManagerServiceClient()
        self._cache: dict[str, Optional[str]] = {}

    def _secret_resource(self, secret_name: str) -> str:
        return f"projects/{self._project_id}/secrets/{secret_name}/versions/latest"

    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]

        name = self._secret_resource(key)

        try:
            response = self._client.access_secret_version(name=name)
        except gcp_exceptions.NotFound:
            logger.warning(
                f"Secret '{key}' not found in GCP project '{self._project_id}'."
            )
            self._cache[key] = None
            return None
        except gcp_exceptions.GoogleAPICallError as exc:
            raise RuntimeError(
                "Failed to access secret "
                f"'{key}' in GCP project '{self._project_id}': {exc}"
            ) from exc
        except gcp_exceptions.RetryError as exc:  # pragma: no cover - seldom triggered
            raise RuntimeError(
                "Retry exhausted when accessing secret "
                f"'{key}' in GCP project '{self._project_id}': {exc}"
            ) from exc

        payload = response.payload.data.decode("utf-8")
        self._cache[key] = payload
        return payload

    def get_many(self, keys: list[str]) -> dict[str, Optional[str]]:
        return {key: self.get(key) for key in keys}

    @property
    def project_id(self) -> str:
        """Return the configured GCP project identifier."""

        return self._project_id
