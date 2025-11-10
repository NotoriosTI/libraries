from __future__ import annotations

import logging

from src.adapters.chatwoot_real import ChatwootRESTAdapter
from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.env_manager import get_config
from src.interfaces.protocols import ChatwootAdapter

logger = logging.getLogger(__name__)


def get_chatwoot_adapter(env: str) -> ChatwootAdapter:
	if env == "production":
		cfg_base_url = str(get_config("CHATWOOT_BASE_URL"))
		cfg_api_key = str(get_config("CHATWOOT_API_KEY"))
		cfg_account_id = str(get_config("CHATWOOT_ACCOUNT_ID"))
		logger.info("Initialising real Chatwoot REST adapter")
		return ChatwootRESTAdapter(cfg_base_url, cfg_api_key, cfg_account_id)

	logger.info("Initialising mock Chatwoot adapter for env=%s", env)
	return MockChatwootAdapter()


__all__ = ["get_chatwoot_adapter", "ChatwootRESTAdapter", "MockChatwootAdapter"]
