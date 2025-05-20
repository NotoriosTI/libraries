import requests
from typing import Optional
from configuration.application_settings import settings


class ShopifyAdminAPI:
    """Service for interacting with Shopify Admin API"""
    
    def __init__(self, shop_url: Optional[str] = None, api_password: Optional[str] = None, api_version: Optional[str] = None):
        self.shop_url = shop_url if shop_url else settings.SHOPIFY_SHOP_URL
        self.api_password = api_password if api_password else settings.SHOPIFY_TOKEN_API_ADMIN
        self.api_version = api_version if api_version else settings.SHOPIFY_API_VERSION
        self.shop_url = self.shop_url.rstrip('/')
        self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        self.base_url = f"{self.shop_url}/admin/api/{self.api_version}"
        self.last_response = None
        
        # Ensure base_url ends with a slash
        if not self.base_url.endswith('/'):
            self.base_url += '/'
            
    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_password
        }

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

    def read(self, resource, params={}):
        """
        Make a GET request to the Shopify API
        
        Args:
            resource (str): API resource path
            params (dict): Query parameters
            
        Returns:
            dict: JSON response from the API
        """
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

