import requests
from .application_settings import settings, get_graphql_settings

class ShopifyAPI:
    def __init__(self, shop_url=None, api_password=None, api_version="2025-01", agent="emilia"):
        # Cargar configuración desde el archivo .env usando pydantic-settings
        try:
            # Obtener settings específicos para el agente
            agent_settings = get_graphql_settings(agent) if agent != "emilia" else settings
            
            self.shop_url = shop_url if shop_url else agent_settings.SHOPIFY_SHOP_URL
            self.api_password = api_password if api_password else agent_settings.SHOPIFY_TOKEN_API_ADMIN
            self.api_version = api_version if api_version else agent_settings.SHOPIFY_API_VERSION
        except Exception as e:
            # Si hay error con el .env y no se proporcionaron credenciales, lanzar error
            if not (shop_url and api_password):
                raise Exception(f"Error cargando credenciales: {e}. Proporcione shop_url y api_password.")
            # Si se proporcionaron credenciales directamente, usarlas
            self.shop_url = shop_url
            self.api_password = api_password
            self.api_version = api_version
        
        # Asegurar que shop_url no termine con una barra y configurar URLs
        if self.shop_url:
            self.shop_url = self.shop_url.rstrip('/')
            self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
            self.base_url = f"{self.shop_url}/admin/api/{self.api_version}"
        
        # Inicializar last_response
        self.last_response = None

        # Asegúrate de que la base_url termine con una barra
        if self.base_url and not self.base_url.endswith('/'):
            self.base_url += '/'

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_password
        }

    # GraphQL específico - ejecuta queries y mutations
    def execute_graphql(self, query, variables=None):
        """
        Execute a GraphQL query or mutation
        
        Args:
            query (str): GraphQL query or mutation
            variables (dict): Variables for the query
            
        Returns:
            dict: JSON response from the API
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

    # Mantener compatibilidad con métodos REST
    def read(self, resource, params={}):
        url = f"{self.base_url}/{resource}"
        response = requests.get(url, headers=self.get_headers(), params=params)
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def put(self, endpoint, **kwargs):
        """
        Make a PUT request to the Shopify API
        
        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to requests.put
            
        Returns:
            dict: JSON response from the API
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.put(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, **kwargs):
        """
        Make a POST request to the Shopify API
        
        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to requests.post
            
        Returns:
            dict: JSON response from the API
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint, **kwargs):
        """
        Make a DELETE request to the Shopify API
        
        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to requests.delete
            
        Returns:
            dict: JSON response from the API
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.delete(url, headers=self.get_headers(), **kwargs)
        self.last_response = response
        response.raise_for_status()
        return response.json() if response.text else None