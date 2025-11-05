from typing import Optional

from src.adapters.base_db_adapter import BaseDBAdapter
from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter

_db_adapter: Optional[BaseDBAdapter] = None
_chatwoot_adapter: Optional[MockChatwootAdapter] = None


def set_db_adapter(adapter: BaseDBAdapter) -> None:
    global _db_adapter
    _db_adapter = adapter


def get_db_adapter() -> BaseDBAdapter:
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
