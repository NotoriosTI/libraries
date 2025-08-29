# configuration/application_settings.py
"""Application configuration settings for Shopify GraphQL API using config-manager."""

from config_manager import secrets


class GraphQLSettings:
    """GraphQL-specific settings using centralized config-manager."""
    
    def __init__(self):
        # Obtener configuración desde config-manager
        shopify_config = secrets.get_shopify_config(use_admin_api=True)
        
        # Shopify Configuration
        self.SHOPIFY_SHOP_URL = shopify_config.get('shop_url')
        self.SHOPIFY_API_VERSION = shopify_config.get('api_version', '2025-01')
        self.SHOPIFY_TOKEN_API_ADMIN = shopify_config.get('admin_token')
        
        # Validar configuración requerida
        if not self.SHOPIFY_SHOP_URL:
            raise ValueError("EMILIA_SHOPIFY_SHOP_URL no está configurado en config-manager")
        if not self.SHOPIFY_TOKEN_API_ADMIN:
            raise ValueError("EMILIA_SHOPIFY_TOKEN_API_ADMIN no está configurado en config-manager")


# Create settings instance
settings = GraphQLSettings()
