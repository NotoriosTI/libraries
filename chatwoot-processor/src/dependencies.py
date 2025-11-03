from typing import Optional

from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.adapters.mock_db_adapter import MockDBAdapter

_db_adapter: Optional[MockDBAdapter] = None
_chatwoot_adapter: Optional[MockChatwootAdapter] = None


def set_db_adapter(adapter: MockDBAdapter) -> None:
    global _db_adapter
    _db_adapter = adapter


def get_db_adapter() -> MockDBAdapter:
    if _db_adapter is None:
        raise RuntimeError("Database adapter has not been configured")
    return _db_adapter


def set_chatwoot_adapter(adapter: MockChatwootAdapter) -> None:
    global _chatwoot_adapter
    _chatwoot_adapter = adapter


def get_chatwoot_adapter() -> MockChatwootAdapter:
    if _chatwoot_adapter is None:
        raise RuntimeError("Chatwoot adapter has not been configured")
    return _chatwoot_adapter
