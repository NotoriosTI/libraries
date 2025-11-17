from __future__ import annotations

from src.adapters.chatwoot_real import ChatwootRESTAdapter as _ChatwootRESTAdapter
from src.env_manager import get_config


class ChatwootRESTAdapter(_ChatwootRESTAdapter):
    """Backward compatible wrapper that bootstraps configuration automatically."""

    def __init__(self) -> None:
        base_url = str(get_config("CHATWOOT_BASE_URL"))
        api_key = str(get_config("CHATWOOT_API_KEY"))
        account_id = str(get_config("CHATWOOT_ACCOUNT_ID"))
        super().__init__(base_url, api_key, account_id)


__all__ = ["ChatwootRESTAdapter"]
