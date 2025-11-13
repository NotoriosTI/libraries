"""
Configuration adapter for product-engine using env-manager.

This module provides unified configuration management, automatically reading and 
validating secrets from local .env files or Google Cloud Secret Manager 
(GCP), based on environment settings.
"""
from typing import Dict, Optional
from env_manager import init_config, get_config, require_config
import structlog

logger = structlog.get_logger(__name__)

    # One-time explicit initialization of env-manager
try:
    init_config(
        "config/config_vars.yaml",
        secret_origin=None,
        gcp_project_id=None,
        strict=None,
        dotenv_path=None,
        debug=True,
    )
    # Verify that the environment has loaded and log in.
    current_env = require_config("ENVIRONMENT")

    logger.bind(component="product_config").info(
        "configuration initialized",
        environment=current_env
    )
except RuntimeError as e:
    # Captures initialization errors
    logger.error("Configuration initialization failed", error=str(e))
    raise
except ValueError as e:
    # Captures validation errors
    logger.error("configuration validation failed", error=str(e))
    raise

class ProductEngineConfig:
    # Configuration manager for the product engine.(Now an Adapter)
    def get_odoo_config(self, use_test: bool = False) -> Dict[str, str]:
        """Get the Odoo configuration."""
        return {
            "url": get_config("ODOO_PROD_URL"),
            "db": get_config("ODOO_PROD_DB"),
            "username": get_config("ODOO_PROD_USERNAME"),
            "password": get_config("ODOO_PROD_PASSWORD")
        }
    
    def get_database_config(self) -> Dict[str, str]:
        """Gets the database configuration."""
        return {
            "host": get_config("PRODUCT_DB_HOST"),
            "port": str(get_config("PRODUCT_DB_PORT")),
            "name": get_config("PRODUCT_DB_NAME"),
            "user": get_config("PRODUCT_DB_USER"),
            "password": get_config("PRODUCT_DB_PASSWORD"),
        }

    def get_openai_api_key(self) -> str:
        """Get the OpenAI key."""
        return require_config("OPENAI_API_KEY")

    @property
    def environment(self) -> str:
        """obtains the current environment."""
        return require_config("ENVIRONMENT")

    @property
    def is_production(self) -> bool:
        """Check if it is running in production."""
        return self.environment == 'production'

    @property
    def is_development(self) -> bool:
        """Check if it is running in development."""
        return self.environment in ('local_machine', 'local_container')


# Singleton instance
config = ProductEngineConfig() 