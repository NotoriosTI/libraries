# configuration/application_settings.py
"""Application configuration settings for Shopify GraphQL API using config-manager."""

from config_manager import secrets


class GraphQLSettings:
    """GraphQL-specific settings using centralized config-manager."""
    
    def __init__(self, agent="emilia"):
        # Obtener configuración desde config-manager según el agente
        if agent.lower() == "emma":
            shopify_config = secrets.get_emma_shopify_config(use_admin_api=True)
        else:
            # Default a emilia para compatibilidad con código existente
            shopify_config = secrets.get_shopify_config(use_admin_api=True)
        
        # Shopify Configuration
        self.SHOPIFY_SHOP_URL = shopify_config.get('shop_url')
        self.SHOPIFY_API_VERSION = shopify_config.get('api_version', '2025-01')
        self.SHOPIFY_TOKEN_API_ADMIN = shopify_config.get('admin_token')
        
        # Validar configuración requerida
        if not self.SHOPIFY_SHOP_URL:
            agent_prefix = agent.upper()
            raise ValueError(f"{agent_prefix}_SHOPIFY_SHOP_URL no está configurado en config-manager")
        if not self.SHOPIFY_TOKEN_API_ADMIN:
            agent_prefix = agent.upper()
            raise ValueError(f"{agent_prefix}_SHOPIFY_TOKEN_API_ADMIN no está configurado en config-manager")


# Lazy loading para evitar errores en import
_default_settings = None

def _get_default_settings():
    """Lazy loading de settings por defecto."""
    global _default_settings
    if _default_settings is None:
        _default_settings = GraphQLSettings()
    return _default_settings

# Crear una propiedad que se evalúe bajo demanda
class SettingsProxy:
    def __getattr__(self, name):
        return getattr(_get_default_settings(), name)

# Create default settings instance for backward compatibility
settings = SettingsProxy()

def get_graphql_settings(agent="emilia"):
    """Get GraphQL settings for a specific agent."""
    return GraphQLSettings(agent=agent)
