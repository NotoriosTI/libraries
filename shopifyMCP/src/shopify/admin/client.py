import requests
from typing import Dict, Any, Optional

class ShopifyAdminClient:
    """Cliente base para la API Admin de Shopify (GraphQL)."""
    
    def __init__(self, shop_url: str, admin_token: str, api_version: str = "2025-01"):
        """
        Args:
            shop_url: URL completa (ej. 'https://mitienda.myshopify.com')
            admin_token: Token que empieza con 'shpat_'
            api_version: Versión de API (ej. '2025-01')
        """
        self.shop_url = shop_url.rstrip("/")
        self.api_url = f"{self.shop_url}/admin/api/{api_version}/graphql.json"
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": admin_token
        }

    def execute(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecuta query GraphQL y maneja errores HTTP/GraphQL básicos."""
        payload = {"query": query, "variables": variables or {}}
        
        response = requests.post(self.api_url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Si Shopify devuelve errores en el cuerpo (aunque sea 200 OK)
        if "errors" in data:
            # Aquí podrías levantar una excepción personalizada
            raise Exception(f"Shopify GraphQL Error: {data['errors']}")
            
        return data