"""
Configuration adapter for sales-engine using shared config-manager.
"""
from typing import Dict, str
from config_manager import secrets

def get_odoo_config(use_test: bool = False) -> Dict[str, str]:
    """Get Odoo configuration from shared config manager."""
    return secrets.get_odoo_config(use_test=use_test)

def get_database_config() -> Dict[str, str]:
    """Get database configuration from shared config manager."""
    return secrets.get_database_config()