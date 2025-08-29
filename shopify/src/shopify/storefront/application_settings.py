# configuration/application_settings.py
"""Application configuration settings for Shopify Storefront API using config-manager."""

from config_manager import secrets


class StorefrontSettings:
    """Storefront-specific settings using centralized config-manager."""
    
    def __init__(self):
        # Obtener configuración desde config-manager
        shopify_config = secrets.get_shopify_config(use_admin_api=False)
        
        # Shopify Configuration
        self.SHOPIFY_SHOP_URL = shopify_config.get('shop_url')
        self.SHOPIFY_API_VERSION = shopify_config.get('api_version', '2025-01')
        self.SHOPIFY_TOKEN_API_STOREFRONT = shopify_config.get('storefront_token')
        
        # Validar configuración requerida
        if not self.SHOPIFY_SHOP_URL:
            raise ValueError("EMILIA_SHOPIFY_SHOP_URL no está configurado en config-manager")
        if not self.SHOPIFY_TOKEN_API_STOREFRONT:
            raise ValueError("EMILIA_SHOPIFY_TOKEN_API_STOREFRONT no está configurado en config-manager")


# Create settings instance
settings = StorefrontSettings()
