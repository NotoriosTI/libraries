from bs4 import BeautifulSoup
from typing import List, Dict, Union, Optional
from .client import ShopifyAdminClient

class ShopifyProductManager:
    def __init__(self, client: ShopifyAdminClient):
        self.client = client

    def search_products(self, query_term: str, limit: int = 5) -> List[Dict]:
        """
        Busca productos usando sintaxis avanzada de Shopify.
        No hace bucles, usa el motor de búsqueda nativo.
        
        Args:
            query_term: Ej. "title:zapatos AND tag:oferta" o simplemente "zapatos"
        """
        gql_query = """
        query SearchProducts($query: String!, $limit: Int!) {
          products(first: $limit, query: $query) {
            edges {
              node {
                id
                title
                status
                totalInventory
                descriptionHtml
                variants(first: 1) {
                  edges {
                    node {
                      price
                      sku
                    }
                  }
                }
                images(first: 1) {
                  edges { node { url altText } }
                }
              }
            }
          }
        }
        """
        
        response = self.client.execute(gql_query, {"query": query_term, "limit": limit})
        edges = response.get("data", {}).get("products", {}).get("edges", [])
        
        results = []
        for edge in edges:
            node = edge["node"]
            
            # Procesamiento de datos (Flattening)
            price = "0"
            sku = ""
            if node["variants"]["edges"]:
                v = node["variants"]["edges"][0]["node"]
                price = v["price"]
                sku = v["sku"]

            # Limpieza HTML (Opcional, pero recomendado tenerlo aquí)
            desc_text = ""
            if node.get("descriptionHtml"):
                soup = BeautifulSoup(node["descriptionHtml"], "html.parser")
                desc_text = soup.get_text(separator=" ", strip=True)[:300]

            results.append({
                "id": node["id"].split("/")[-1], # ID Numérico limpio
                "title": node["title"],
                "status": node["status"],
                "sku_ref": sku,
                "price_ref": price,
                "stock_total": node["totalInventory"],
                "summary": desc_text
            })
            
        return results

    def read_product_info(self, identifier: str) -> Optional[Dict]:
        """
        Obtiene ficha completa por ID o SKU.
        Detecta automáticamente el tipo de identificador.
        """
        # 1. Estrategia de búsqueda (ID vs SKU)
        # Si es numérico puro, asumimos ID. Si no, SKU.
        is_id = identifier.isdigit()
        
        search_query = f"id:{identifier}" if is_id else f"sku:{identifier}"
        
        gql_query = """
        query GetProductDetail($q: String!) {
          products(first: 1, query: $q) {
            edges {
              node {
                id
                title
                productType
                vendor
                status
                descriptionHtml
                tags
                options { name values }
                images(first: 5) { edges { node { url } } }
                variants(first: 50) {
                  edges {
                    node {
                      id
                      title
                      sku
                      price
                      inventoryQuantity
                      barcode
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        response = self.client.execute(gql_query, {"q": search_query})
        edges = response.get("data", {}).get("products", {}).get("edges", [])
        
        if not edges:
            return None # O lanzar excepción ProductNotFound
            
        prod = edges[0]["node"]
        
        # 2. Limpieza y Estructuración
        full_desc = ""
        if prod.get("descriptionHtml"):
            soup = BeautifulSoup(prod["descriptionHtml"], "html.parser")
            full_desc = soup.get_text(separator="\n", strip=True)

        variants = []
        for v in prod["variants"]["edges"]:
            node = v["node"]
            variants.append({
                "id": node["id"].split("/")[-1],
                "title": node["title"],
                "sku": node["sku"],
                "price": node["price"],
                "stock": node["inventoryQuantity"],
                "barcode": node["barcode"]
            })

        return {
            "id": prod["id"].split("/")[-1],
            "title": prod["title"],
            "vendor": prod["vendor"],
            "type": prod["productType"],
            "status": prod["status"],
            "tags": prod["tags"],
            "description": full_desc,
            "options": [{"name": o["name"], "values": o["values"]} for o in prod["options"]],
            "variants": variants,
            "images": [i["node"]["url"] for i in prod["images"]["edges"]]
        }