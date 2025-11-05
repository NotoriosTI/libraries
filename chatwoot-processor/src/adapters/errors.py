from __future__ import annotations

from typing import Any


class ChatwootAdapterError(RuntimeError):
    """Custom error raised when Chatwoot adapters fail to deliver messages."""

    def __init__(self, message: str, *, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload: dict[str, Any] = payload or {}


__all__ = ["ChatwootAdapterError"]
