"""
Configuration adapter for product-engine using shared config-manager.

This module provides configuration management that reads from .env files in 
development and Google Secret Manager in production.
"""
from typing import Dict, Optional
from config_manager import secrets
import structlog

logger = structlog.get_logger(__name__)

class ProductEngineConfig:
    """Configuration manager for the product engine."""
    
    def __init__(self):
        """Initialize configuration using the shared config manager."""
        self.config = secrets
        self.logger = logger.bind(component="product_config")
        
        # Validate required configuration
        self._validate_config()
        
        self.logger.info(
            "Configuration initialized",
            environment=self.config.ENVIRONMENT
        )
    
    def _validate_config(self):
        """Validate that all required configuration is present."""
        required_fields = [
            'ODOO_PROD_URL', 'ODOO_PROD_DB', 'ODOO_PROD_USERNAME', 'ODOO_PROD_PASSWORD',
            'PRODUCT_DB_HOST', 'PRODUCT_DB_PORT', 'PRODUCT_DB_NAME', 'PRODUCT_DB_USER', 'PRODUCT_DB_PASSWORD',
            'OPENAI_API_KEY'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(self.config, field) or not getattr(self.config, field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")
    
    def get_odoo_config(self, use_test: bool = False) -> Dict[str, str]:
        """Get Odoo configuration from shared config manager."""
        return self.config.get_odoo_config(use_test=use_test)
    
    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration from shared config manager."""
        return self.config.get_product_database_config()
    
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key."""
        if not self.config.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not configured")
        return self.config.OPENAI_API_KEY
    
    @property
    def environment(self) -> str:
        """Get current environment."""
        return self.config.ENVIRONMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.config.ENVIRONMENT == 'production'
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.config.ENVIRONMENT in ('local_machine', 'local_container')

# Singleton instance
config = ProductEngineConfig() 