# configuration/application_settings.py
"""
Application configuration settings for Shopify GraphQL API using config-manager.

Este módulo proporciona configuración para la API GraphQL de Shopify.
Soporta dos modos de operación:

1. MODO EMMA (Nuevo):
   Las credenciales se inicializan explícitamente en el proyecto Emma
   y se pasan directamente al cliente ShopifyAPI.
   La librería NO carga configuración de este módulo en ese caso.

2. MODO EMILIA (Legacy - Por compatibilidad):
   Las credenciales se cargan automáticamente de config-manager.
   Este modo está deprecado pero se mantiene para compatibilidad con código existente.

RECOMENDACIÓN:
Para nuevos proyectos (como Emma), inicializa las credenciales en tu proyecto
y pásalas explícitamente a ShopifyAPI. Evita usar este módulo directamente.
"""

from typing import Optional
from config_manager import secrets


class GraphQLSettings:
    """
    Clase para cargar configuración GraphQL desde config-manager.
    
    ⚠️ DEPRECADO: Este módulo está optimizado para Emilia.
    Para Emma, inicializa las credenciales en tu proyecto usando ShopifyAPISecret.
    """
    
    def __init__(self, agent: str = "emilia") -> None:
        """
        Carga la configuración de Shopify GraphQL desde config-manager.
        
        Args:
            agent: Nombre del agente ("emma" o "emilia").
                  Este parámetro solo se usa si intentas cargar config-manager.
                  Para Emma, es recomendable pasar credenciales explícitamente.
        
        Raises:
            ValueError: Si la configuración requerida no está disponible en config-manager
        """
        # Obtener configuración desde config-manager según el agente
        if agent.lower() == "emma":
            shopify_config = secrets.get_emma_shopify_config(use_admin_api=True)
        else:
            # Default a emilia para compatibilidad con código existente
            shopify_config = secrets.get_shopify_config(use_admin_api=True)
        
        # Shopify Configuration
        self.SHOPIFY_SHOP_URL: Optional[str] = shopify_config.get('shop_url')
        self.SHOPIFY_API_VERSION: Optional[str] = shopify_config.get('api_version', '2025-01')
        self.SHOPIFY_TOKEN_API_ADMIN: Optional[str] = shopify_config.get('admin_token')
        
        # Validar configuración requerida
        if not self.SHOPIFY_SHOP_URL:
            agent_prefix = agent.upper()
            raise ValueError(
                f"{agent_prefix}_SHOPIFY_SHOP_URL no está configurado en config-manager. "
                f"Para Emma, inicializa ShopifyAPISecret en tu proyecto."
            )
        if not self.SHOPIFY_TOKEN_API_ADMIN:
            agent_prefix = agent.upper()
            raise ValueError(
                f"{agent_prefix}_SHOPIFY_TOKEN_API_ADMIN no está configurado en config-manager. "
                f"Para Emma, inicializa ShopifyAPISecret en tu proyecto."
            )


# Lazy loading para evitar errores en import
_default_settings: Optional[GraphQLSettings] = None


def _get_default_settings() -> GraphQLSettings:
    """
    Lazy loading de settings por defecto.
    
    Solo se evalúa cuando se accede por primera vez a 'settings'.
    Esto permite que la inicialización sea perezosa.
    """
    global _default_settings
    if _default_settings is None:
        _default_settings = GraphQLSettings()
    return _default_settings


# Proxy para lazy loading de settings
class SettingsProxy:
    """
    Proxy que carga los settings de manera perezosa.
    
    Permite evitar errores de importación si config-manager no está disponible
    en el momento de importar este módulo.
    """
    
    def __getattr__(self, name: str):
        """Delega atributos al objeto settings cargado."""
        return getattr(_get_default_settings(), name)


# Create default settings instance for backward compatibility
settings = SettingsProxy()


def get_graphql_settings(agent: str = "emilia") -> GraphQLSettings:
    """
    Obtiene la configuración GraphQL para un agente específico.
    
    ⚠️ DEPRECADO: Este módulo está optimizado para Emilia.
    Para Emma, inicializa las credenciales en tu proyecto.
    
    Args:
        agent: Nombre del agente ("emma" o "emilia")
        
    Returns:
        Instancia de GraphQLSettings con la configuración del agente
        
    Raises:
        ValueError: Si la configuración no está disponible en config-manager
    
    Examples:
        # Legacy - Para Emilia (mantener para compatibilidad)
        settings = get_graphql_settings("emilia")
        
        # Para Emma, es mejor:
        # 1. Inicializar en tu proyecto
        from config_manager.emma import ShopifyAPISecret
        shopify_secret = ShopifyAPISecret()
        # 2. Pasar explícitamente a ShopifyAPI
        from shopify.graphql import ShopifyAPI
        api = ShopifyAPI(
            shop_url=shopify_secret.url,
            api_password=shopify_secret.admin_token
        )
    """
    return GraphQLSettings(agent=agent)

