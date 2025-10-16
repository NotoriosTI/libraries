from typing import Optional, Dict, Any
import requests
from .application_settings import settings, get_storefront_settings


class StorefrontAPI:
    """
    Cliente para interactuar con la API de Shopify Storefront GraphQL.
    
    Soporta dos modos de operación:
    
    1. MODO EMMA (Nuevo - Recomendado):
       Las credenciales se pasan explícitamente desde el proyecto Emma.
       Ideal para separar la configuración del negocio de la librería.
       
       >>> storefront = StorefrontAPI(
       ...     shop_url="https://mi-tienda.myshopify.com",
       ...     storefront_access_token="...",
       ...     agent="emma"
       ... )
    
    2. MODO EMILIA (Legacy - Para compatibilidad):
       Las credenciales se cargan automáticamente de config-manager.
       Mantiene compatibilidad con código existente.
       
       >>> storefront = StorefrontAPI()  # Usa agent="emilia" por defecto
    """

    def __init__(
        self,
        shop_url: Optional[str] = None,
        storefront_access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        agent: str = "emilia"
    ) -> None:
        """
        Inicializa el cliente de Shopify Storefront API.
        
        Args:
            shop_url: URL de la tienda Shopify (ej: https://mi-tienda.myshopify.com).
                     Requerido si se usa con credenciales explícitas.
            storefront_access_token: Token de acceso público para Storefront API.
                                    Requerido si se usa con credenciales explícitas.
            api_version: Versión de la API de Shopify. Si no se proporciona, usa default.
            agent: "emma" o "emilia" - determina cómo se cargan las credenciales.
                  - "emma": Requiere shop_url y storefront_access_token explícitos
                  - "emilia": Carga credenciales de config-manager (legacy)
                  Default: "emilia" (para compatibilidad)
        
        Raises:
            ValueError: Si faltan credenciales requeridas o no se pueden cargar.
        
        Examples:
            # Modo Emma (explícito - recomendado)
            api = StorefrontAPI(
                shop_url="https://tienda.myshopify.com",
                storefront_access_token="abcd1234...",
                agent="emma"
            )
            
            # Modo Emilia (legacy - automático desde config-manager)
            api = StorefrontAPI()
        """
        
        # Lógica de decisión clara:
        # Si se proporcionan AMBAS credenciales explícitamente → usar modo Emma
        # Si NO se proporcionan → usar modo Emilia (cargar de config-manager)
        
        if shop_url is not None and storefront_access_token is not None:
            # MODO EMMA: Credenciales explícitas
            self._initialize_explicit(shop_url, storefront_access_token, api_version)
        else:
            # MODO EMILIA (LEGACY): Cargar de config-manager
            self._initialize_from_config_manager(
                agent, shop_url, storefront_access_token, api_version
            )

    def _initialize_explicit(
        self,
        shop_url: str,
        storefront_access_token: str,
        api_version: Optional[str]
    ) -> None:
        """
        Inicialización con credenciales explícitas (Modo Emma).
        
        Este método es llamado cuando se proporcionan credenciales directamente
        al constructor.
        
        Args:
            shop_url: URL de la tienda Shopify
            storefront_access_token: Token de acceso Storefront
            api_version: Versión de la API
        """
        self.shop_url = shop_url.rstrip('/')
        self.storefront_access_token = storefront_access_token
        self.api_version = api_version or "2025-01"
        self.graphql_url = f"{self.shop_url}/api/{self.api_version}/graphql"
        self.last_response = None

    def _initialize_from_config_manager(
        self,
        agent: str,
        shop_url: Optional[str],
        storefront_access_token: Optional[str],
        api_version: Optional[str]
    ) -> None:
        """
        Inicialización desde config-manager (Modo Emilia - Legacy).
        
        Este método intenta cargar las credenciales desde config-manager.
        Solo funciona si config-manager está correctamente configurado.
        
        Args:
            agent: Nombre del agente ("emilia" o "emma")
            shop_url: URL de tienda (usado como fallback)
            storefront_access_token: Token Storefront (usado como fallback)
            api_version: Versión de la API
        
        Raises:
            ValueError: Si no se pueden cargar las credenciales
        """
        try:
            agent_settings = (
                get_storefront_settings(agent) if agent != "emilia" else settings
            )
            shop_url = shop_url or agent_settings.SHOPIFY_SHOP_URL
            storefront_access_token = (
                storefront_access_token or agent_settings.SHOPIFY_TOKEN_API_STOREFRONT
            )
            api_version = api_version or agent_settings.SHOPIFY_API_VERSION
        except Exception as e:
            raise ValueError(
                f"Error al cargar credenciales de Shopify Storefront para agent='{agent}': {e}. "
                f"Para Emma, proporcione shop_url y storefront_access_token explícitamente. "
                f"Para Emilia, verifique la configuración de config-manager."
            )

        if not shop_url or not storefront_access_token:
            raise ValueError(
                f"Credenciales incompletas para Shopify Storefront (agent='{agent}'). "
                f"Proporcione tanto shop_url como storefront_access_token, "
                f"o use ShopifyAPISecret en el proyecto Emma."
            )

        self._initialize_explicit(shop_url, storefront_access_token, api_version)

    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene los headers HTTP requeridos para las solicitudes a la API.
        
        Returns:
            Dict[str, str]: Diccionario con headers de autorización
        """
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Storefront-Access-Token': self.storefront_access_token
        }

    def execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta una consulta o mutación GraphQL contra la API Storefront.
        
        Args:
            query: Consulta o mutación GraphQL (string)
            variables: Variables para la consulta GraphQL (opcional)
            
        Returns:
            Respuesta JSON de la API como diccionario
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        
        Examples:
            >>> query = 'query { shop { name } }'
            >>> result = storefront.execute_graphql(query)
        """
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        response = requests.post(
            self.graphql_url,
            headers=self.get_headers(),
            json=payload
        )
        
        self.last_response = response
        response.raise_for_status()
        return response.json()