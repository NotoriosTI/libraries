# configuration/application_settings.py
"""Application configuration settings for Shopify Storefront API using config-manager."""

from config_manager import secrets


class StorefrontSettings:
    """Storefront-specific settings using centralized config-manager."""
    
    def __init__(self, agent="emilia"):
        # Obtener configuración desde config-manager según el agente
        if agent.lower() == "emma":
            shopify_config = secrets.get_emma_shopify_config(use_admin_api=False)
        else:
            # Default a emilia para compatibilidad con código existente
            shopify_config = secrets.get_shopify_config(use_admin_api=False)
        
        # Shopify Configuration
        self.SHOPIFY_SHOP_URL = shopify_config.get('shop_url')
        self.SHOPIFY_API_VERSION = shopify_config.get('api_version', '2025-01')
        self.SHOPIFY_TOKEN_API_STOREFRONT = shopify_config.get('storefront_token')
        
        # Validar configuración requerida
        if not self.SHOPIFY_SHOP_URL:
            agent_prefix = agent.upper()
            raise ValueError(f"{agent_prefix}_SHOPIFY_SHOP_URL no está configurado en config-manager")
        if not self.SHOPIFY_TOKEN_API_STOREFRONT:
            agent_prefix = agent.upper()
            raise ValueError(f"{agent_prefix}_SHOPIFY_TOKEN_API_STOREFRONT no está configurado en config-manager")


# Lazy loading para evitar errores en import
_default_settings = None

def _get_default_settings():
    """Lazy loading de settings por defecto."""
    global _default_settings
    if _default_settings is None:
        _default_settings = StorefrontSettings()
    return _default_settings

# Crear una propiedad que se evalúe bajo demanda
class SettingsProxy:
    def __getattr__(self, name):
        return getattr(_get_default_settings(), name)

# Create default settings instance for backward compatibility
settings = SettingsProxy()

def get_storefront_settings(agent="emilia"):
    """Get Storefront settings for a specific agent."""
    return StorefrontSettings(agent=agent)
