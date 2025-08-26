from decouple import Config, RepositoryEnv
import requests

dotenv_path = '/home/snparada/Spacionatural/Libraries/shopify_graph_lib/creds/.env'
config = Config(RepositoryEnv(dotenv_path))

class ShopifyAPI:
    def __init__(self, shop_url=None, api_password=None, api_version="2025-01"):
        # Leer las variables de entorno utilizando decouple
        self.shop_url = shop_url if shop_url else config('SHOPIFY_SHOP_URL')
        self.api_password = api_password if api_password else config('SHOPIFY_PASSWORD')
        self.api_version = api_version if api_version else config('SHOPIFY_API_VERSION')
        self.shop_url = self.shop_url.rstrip('/')
        self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        self.base_url = f"{self.shop_url}/admin/api/{self.api_version}"
        self.last_response = None

        # Asegúrate de que la base_url termine con una barra
        if not self.base_url.endswith('/'):
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