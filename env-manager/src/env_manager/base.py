"""Protocol definitions for secret loaders."""

from typing import Optional, Protocol


class SecretLoader(Protocol):
    """Interface that all secret loaders must implement."""

    def get(self, key: str) -> Optional[str]:
        """Retrieve a single secret by key."""

    def get_many(self, keys: list[str]) -> dict[str, Optional[str]]:
        """Retrieve multiple secrets efficiently."""
