import requests
from .application_settings import settings, get_storefront_settings


class StorefrontAPI:
    def __init__(self, shop_url=None, storefront_access_token=None, api_version=None, agent="emilia"):
        # Cargar configuración desde el archivo .env
        try:
            # Obtener settings específicos para el agente
            agent_settings = get_storefront_settings(agent) if agent != "emilia" else settings
            
            self.shop_url = shop_url if shop_url else agent_settings.SHOPIFY_SHOP_URL
            self.storefront_access_token = storefront_access_token if storefront_access_token else agent_settings.SHOPIFY_TOKEN_API_STOREFRONT
            self.api_version = api_version if api_version else agent_settings.SHOPIFY_API_VERSION
        except Exception as e:
            # Si hay error con el .env y no se proporcionaron credenciales, lanzar error
            if not (shop_url and storefront_access_token):
                raise Exception(f"Error cargando credenciales: {e}. Proporcione shop_url y storefront_access_token.")
            # Si se proporcionaron credenciales directamente, usarlas
            self.shop_url = shop_url
            self.storefront_access_token = storefront_access_token
            self.api_version = api_version
        
        # Asegurar que shop_url no termine con una barra
        if self.shop_url:
            self.shop_url = self.shop_url.rstrip('/')
            self.graphql_url = f"{self.shop_url}/api/{self.api_version}/graphql"
        
        # Inicializar last_response
        self.last_response = None

    def get_headers(self):
        """
        Obtener los encabezados HTTP para las solicitudes a la API de Storefront
        """
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Storefront-Access-Token': self.storefront_access_token
        }

    def execute_graphql(self, query, variables=None):
        """
        Ejecutar una consulta GraphQL contra la API de Storefront
        
        Args:
            query (str): Consulta o mutación GraphQL
            variables (dict): Variables para la consulta
            
        Returns:
            dict: Respuesta JSON de la API
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