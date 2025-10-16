from typing import Optional, Dict, Any
import requests
from .application_settings import settings, get_graphql_settings


class ShopifyAPI:
    """
    Cliente para interactuar con la API de Shopify GraphQL (Admin API).
    
    Soporta dos modos de operación:
    
    1. MODO EMMA (Nuevo - Recomendado):
       Las credenciales se pasan explícitamente desde el proyecto Emma.
       Ideal para separar la configuración del negocio de la librería.
       
       >>> shopify = ShopifyAPI(
       ...     shop_url="https://mi-tienda.myshopify.com",
       ...     api_password="shppa_...",
       ...     agent="emma"
       ... )
    
    2. MODO EMILIA (Legacy - Para compatibilidad):
       Las credenciales se cargan automáticamente de config-manager.
       Mantiene compatibilidad con código existente.
       
       >>> shopify = ShopifyAPI()  # Usa agent="emilia" por defecto
    """

    def __init__(
        self,
        shop_url: Optional[str] = None,
        api_password: Optional[str] = None,
        api_version: str = "2025-01",
        agent: str = "emilia"
    ) -> None:
        """
        Inicializa el cliente de Shopify GraphQL API.
        
        Args:
            shop_url: URL de la tienda Shopify (ej: https://mi-tienda.myshopify.com).
                     Requerido si se usa con credenciales explícitas.
            api_password: Token de acceso para Admin API.
                         Requerido si se usa con credenciales explícitas.
            api_version: Versión de la API de Shopify. Default: "2025-01"
            agent: "emma" o "emilia" - determina cómo se cargan las credenciales.
                  - "emma": Requiere shop_url y api_password explícitos
                  - "emilia": Carga credenciales de config-manager (legacy)
                  Default: "emilia" (para compatibilidad)
        
        Raises:
            ValueError: Si faltan credenciales requeridas o no se pueden cargar.
        
        Examples:
            # Modo Emma (explícito - recomendado)
            api = ShopifyAPI(
                shop_url="https://tienda.myshopify.com",
                api_password="shppa_abc123...",
                agent="emma"
            )
            
            # Modo Emilia (legacy - automático desde config-manager)
            api = ShopifyAPI()
        """
        
        # Lógica de decisión clara:
        # Si se proporcionan AMBAS credenciales explícitamente → usar modo Emma
        # Si NO se proporcionan → usar modo Emilia (cargar de config-manager)
        
        if shop_url is not None and api_password is not None:
            # MODO EMMA: Credenciales explícitas
            self._initialize_explicit(shop_url, api_password, api_version)
        else:
            # MODO EMILIA (LEGACY): Cargar de config-manager
            self._initialize_from_config_manager(agent, shop_url, api_password, api_version)

    def _initialize_explicit(
        self,
        shop_url: str,
        api_password: str,
        api_version: str
    ) -> None:
        """
        Inicialización con credenciales explícitas (Modo Emma).
        
        Este método es llamado cuando se proporcionan credenciales directamente
        al constructor.
        
        Args:
            shop_url: URL de la tienda Shopify
            api_password: Token de acceso Admin
            api_version: Versión de la API
        """
        self.shop_url = shop_url.rstrip('/')
        self.api_password = api_password
        self.api_version = api_version
        self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        self.base_url = f"{self.shop_url}/admin/api/{self.api_version}/"
        self.last_response = None

    def _initialize_from_config_manager(
        self,
        agent: str,
        shop_url: Optional[str],
        api_password: Optional[str],
        api_version: str
    ) -> None:
        """
        Inicialización desde config-manager (Modo Emilia - Legacy).
        
        Este método intenta cargar las credenciales desde config-manager.
        Solo funciona si config-manager está correctamente configurado.
        
        Args:
            agent: Nombre del agente ("emilia" o "emma")
            shop_url: URL de tienda (usado como fallback)
            api_password: Token API (usado como fallback)
            api_version: Versión de la API
        
        Raises:
            ValueError: Si no se pueden cargar las credenciales
        """
        try:
            agent_settings = get_graphql_settings(agent) if agent != "emilia" else settings
            shop_url = shop_url or agent_settings.SHOPIFY_SHOP_URL
            api_password = api_password or agent_settings.SHOPIFY_TOKEN_API_ADMIN
            api_version = api_version or agent_settings.SHOPIFY_API_VERSION
        except Exception as e:
            raise ValueError(
                f"Error al cargar credenciales de Shopify para agent='{agent}': {e}. "
                f"Para Emma, proporcione shop_url y api_password explícitamente. "
                f"Para Emilia, verifique la configuración de config-manager."
            )

        if not shop_url or not api_password:
            raise ValueError(
                f"Credenciales incompletas para Shopify (agent='{agent}'). "
                f"Proporcione tanto shop_url como api_password, "
                f"o use ShopifyAPISecret en el proyecto Emma."
            )

        self._initialize_explicit(shop_url, api_password, api_version)

    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene los headers HTTP requeridos para las solicitudes a la API.
        
        Returns:
            Dict[str, str]: Diccionario con headers de autorización
        """
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_password
        }

    def execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta una consulta o mutación GraphQL contra la API Admin.
        
        Args:
            query: Consulta o mutación GraphQL (string)
            variables: Variables para la consulta GraphQL (opcional)
            
        Returns:
            Respuesta JSON de la API como diccionario
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        
        Examples:
            >>> query = 'query { shop { name } }'
            >>> result = shopify.execute_graphql(query)
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

    def read(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza una solicitud GET a la API REST.
        
        Args:
            resource: Recurso de la API (ej: "products", "orders")
            params: Parámetros de consulta (opcional)
            
        Returns:
            Respuesta JSON de la API como diccionario
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        """
        url = f"{self.base_url}{resource}"
        response = requests.get(url, headers=self.get_headers(), params=params or {})
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def put(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Realiza una solicitud PUT a la API REST.
        
        Args:
            endpoint: Endpoint de la API
            **kwargs: Argumentos adicionales para requests.put
            
        Returns:
            Respuesta JSON de la API como diccionario
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.put(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Realiza una solicitud POST a la API REST.
        
        Args:
            endpoint: Endpoint de la API
            **kwargs: Argumentos adicionales para requests.post
            
        Returns:
            Respuesta JSON de la API como diccionario
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud DELETE a la API REST.
        
        Args:
            endpoint: Endpoint de la API
            **kwargs: Argumentos adicionales para requests.delete
            
        Returns:
            Respuesta JSON de la API como diccionario, o None si no hay contenido
            
        Raises:
            requests.exceptions.HTTPError: Si la solicitud HTTP falla
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.delete(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json() if response.text else None