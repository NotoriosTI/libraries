import pandas as pd
import requests
import json
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .api import ShopifyAPI 

class ShopifyProducts(ShopifyAPI):
    def __init__(self, shop_url=None, api_password=None, api_version="2025-01"):
        super().__init__(shop_url, api_password, api_version)
        
        if not hasattr(self, "execute_graphql"):
            print("ADVERTENCIA: execute_graphql no encontrado en la instancia, definiendo manualmente")
            self.execute_graphql = self._execute_graphql_fallback
            
        self.sku_to_product_id = self.map_sku_to_product_id()
    
    def _execute_graphql_fallback(self, query, variables=None):
        """
        Método de respaldo en caso de que no se herede correctamente
        """
        print("Usando método de respaldo execute_graphql")
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
    
# CRUD - GraphQL versions

    def read_all_products(self, limit=250):
        """
        Read all products using GraphQL pagination
        """
        products = []
        query = """
        query GetProducts($cursor: String, $limit: Int!) {
          products(first: $limit, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                title
                vendor
                descriptionHtml
                productType
                createdAt
                handle
                updatedAt
                publishedAt
                tags
                status
                images(first: 10) {
                  edges {
                    node {
                      id
                      url
                      altText
                    }
                  }
                }
                variants(first: 100) {
                  edges {
                    node {
                      id
                      title
                      compareAtPrice
                      price
                      sku
                      inventoryQuantity
                      inventoryItem {
                        id
                        inventoryLevels(first: 1) {
                          edges {
                            node {
                              available
                              location {
                                id
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "limit": limit,
            "cursor": None
        }
        
        has_next_page = True
        
        while has_next_page:
            result = self.execute_graphql(query, variables)
            
            if "errors" in result:
                print(f"GraphQL Error: {result['errors']}")
                break
                
            product_data = result["data"]["products"]
            
            # Extract products from edges
            for edge in product_data["edges"]:
                # Convert GraphQL ID format to numeric ID
                node = edge["node"]
                node["id"] = self._extract_id_from_gid(node["id"])
                
                # Convert variant IDs and structure
                variants = []
                for variant_edge in node["variants"]["edges"]:
                    variant = variant_edge["node"]
                    variant["id"] = self._extract_id_from_gid(variant["id"])
                    if variant["inventoryItem"]:
                        variant["inventory_item_id"] = self._extract_id_from_gid(variant["inventoryItem"]["id"])
                        
                        # Extract location ID if available
                        if variant["inventoryItem"]["inventoryLevels"]["edges"]:
                            location_edge = variant["inventoryItem"]["inventoryLevels"]["edges"][0]
                            variant["location_id"] = self._extract_id_from_gid(
                                location_edge["node"]["location"]["id"]
                            )
                    variants.append(variant)
                
                # Replace variants structure with simpler list
                node["variants"] = variants
                
                # Convert images
                images = []
                for image_edge in node["images"]["edges"]:
                    image = image_edge["node"]
                    image["id"] = self._extract_id_from_gid(image["id"])
                    image["src"] = image["url"]
                    del image["url"]
                    images.append(image)
                
                # Replace images structure with simpler list
                node["images"] = images
                
                # Convert descriptionHtml to body_html for compatibility
                node["body_html"] = node["descriptionHtml"]
                del node["descriptionHtml"]
                
                products.append(node)
            
            # Check if there's another page
            page_info = product_data["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            
            if has_next_page:
                variables["cursor"] = page_info["endCursor"]
            
        return products

    def read_all_products_in_dataframe(self):
        """
        Read all products and convert to DataFrame
        """
        products = self.read_all_products()
        
        # Expandir las variantes a nivel de filas
        product_rows = []
        for product in products:
            for variant in product['variants']:
                row = {
                    'id': product['id'],
                    'title': product['title'],
                    'vendor': product['vendor'],
                    'body_html': product['body_html'],
                    'product_type': product['product_type'],
                    'created_at': product['createdAt'],
                    'handle': product['handle'],
                    'updated_at': product['updatedAt'],
                    'published_at': product['publishedAt'],
                    'tags': product['tags'],
                    'status': product['status'],
                    'variant_id': variant['id'],
                    'variant_title': variant['title'],
                    'variant_compare_at_price': variant.get('compareAtPrice'),
                    'variant_price': variant['price'],
                    'variant_sku': variant['sku'],
                    'variant_inventory_quantity': variant.get('inventoryQuantity', 0)
                }
                product_rows.append(row)
        
        # Convertir la lista de filas a un DataFrame
        df_products = pd.DataFrame(product_rows)
        
        return df_products

    def read_all_images(self):
        """
        Read all product images
        """
        images = []
        products = self.read_all_products()
        for product in products:
            for image in product['images']:
                image['description'] = product['body_html']
                images.append(image)
        return images

    def read_actual_complementary_products(self, product_id):
        """
        Read complementary products metafield using GraphQL
        """
        query = """
        query GetProductMetafields($productId: ID!) {
          product(id: $productId) {
            metafields(first: 10, namespace: "shopify--discovery--product_recommendation") {
              edges {
                node {
                  id
                  namespace
                  key
                  value
                  type
                }
              }
            }
          }
        }
        """
        
        variables = {
            "productId": f"gid://shopify/Product/{product_id}"
        }
        
        result = self.execute_graphql(query, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return None
            
        metafields = result["data"]["product"]["metafields"]["edges"]
        
        for edge in metafields:
            metafield = edge["node"]
            if metafield["key"] == "complementary_products":
                # Convert GraphQL ID to standard format
                metafield["id"] = self._extract_id_from_gid(metafield["id"])
                return metafield
                
        print(f"No complementary products found for product {product_id}")
        return None

    def read_variant_id_by_sku(self, sku):
        """
        Find variant ID using SKU with GraphQL
        """
        # Primero, intentamos obtener el product_id usando el mapa sku_to_product_id
        product_id = self.sku_to_product_id.get(sku)
        
        if product_id:
            query = """
            query GetProductVariants($productId: ID!) {
              product(id: $productId) {
                variants(first: 100) {
                  edges {
                    node {
                      id
                      sku
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                "productId": f"gid://shopify/Product/{product_id}"
            }
            
            result = self.execute_graphql(query, variables)
            
            if "errors" not in result:
                variants = result["data"]["product"]["variants"]["edges"]
                for edge in variants:
                    variant = edge["node"]
                    if variant["sku"] == sku:
                        return self._extract_id_from_gid(variant["id"])
        
        # Si no encontramos con el product_id, buscamos por SKU en todos los productos
        query = """
        query GetVariantBySku($query: String!) {
          productVariants(first: 1, query: $query) {
            edges {
              node {
                id
                sku
              }
            }
          }
        }
        """
        
        variables = {
            "query": f"sku:{sku}"
        }
        
        result = self.execute_graphql(query, variables)
        
        if "errors" not in result and result["data"]["productVariants"]["edges"]:
            variant = result["data"]["productVariants"]["edges"][0]["node"]
            return self._extract_id_from_gid(variant["id"])
        
        print(f"No se encontró ninguna variante con el SKU: {sku}")
        return None

    def read_product_metafields(self, product_id):
        """
        Read all metafields for a product
        """
        query = """
        query GetProductMetafields($productId: ID!) {
          product(id: $productId) {
            metafields(first: 100) {
              edges {
                node {
                  id
                  namespace
                  key
                  value
                  type
                }
              }
            }
          }
        }
        """
        
        variables = {
            "productId": f"gid://shopify/Product/{product_id}"
        }
        
        result = self.execute_graphql(query, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return None
            
        metafields = []
        for edge in result["data"]["product"]["metafields"]["edges"]:
            metafield = edge["node"]
            metafield["id"] = self._extract_id_from_gid(metafield["id"])
            metafields.append(metafield)
            
        print(f"Metafields for product {product_id}: {json.dumps(metafields, indent=2)}")
        return metafields

    def read_location_id(self, inventory_item_id):
        """
        Get location ID for an inventory item
        """
        query = """
        query GetInventoryLevels($inventoryItemId: ID!) {
          inventoryItem(id: $inventoryItemId) {
            inventoryLevels(first: 1) {
              edges {
                node {
                  location {
                    id
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "inventoryItemId": f"gid://shopify/InventoryItem/{inventory_item_id}"
        }
        
        result = self.execute_graphql(query, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return None
            
        inventory_data = result["data"]["inventoryItem"]["inventoryLevels"]["edges"]
        if inventory_data:
            location_id = self._extract_id_from_gid(inventory_data[0]["node"]["location"]["id"])
            return location_id
        else:
            print(f"No se encontraron niveles de inventario para el inventory_item_id {inventory_item_id}")
            return None

    def read_variant_info_by_sku(self, sku, clean_html=True):
        """
        Busca y retorna el body_html del producto asociado a una variante por SKU.
        
        Args:
            sku (str): El SKU de la variante a buscar
            clean_html (bool): Si es True, limpia las etiquetas HTML y devuelve solo el texto
            
        Returns:
            str: El body_html del producto (limpio o con HTML según el parámetro clean_html)
        """
        # Primero, intentamos obtener el product_id usando el mapa sku_to_product_id
        product_id = self.sku_to_product_id.get(sku)
        body_html = None
        
        if product_id:
            # Si encontramos el product_id, buscamos el producto
            endpoint = f"products/{product_id}.json"
            url = urljoin(self.base_url, endpoint)
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                product_data = response.json()['product']
                # Verificamos que la variante con ese SKU efectivamente pertenece a este producto
                for variant in product_data['variants']:
                    if variant['sku'] == sku:
                        # Obtenemos el body_html
                        body_html = product_data.get('body_html', '')
                        break
        
        # Si no encontramos el producto o la variante usando el mapeo, hacemos una búsqueda directa
        if body_html is None:
            endpoint = f"variants.json?sku={sku}"
            url = urljoin(self.base_url, endpoint)
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                variants = response.json()['variants']
                if variants:
                    # Obtenemos el producto asociado a la variante
                    product_id = variants[0]['product_id']
                    product_endpoint = f"products/{product_id}.json"
                    product_url = urljoin(self.base_url, product_endpoint)
                    product_response = requests.get(product_url, headers=self.get_headers())
                    
                    if product_response.status_code == 200:
                        product_data = product_response.json()['product']
                        # Obtenemos el body_html
                        body_html = product_data.get('body_html', '')
        
        # Si no encontramos nada, retornamos None
        if body_html is None:
            print(f"No se encontró ninguna variante con el SKU: {sku}")
            return None
        
        # Si se solicita limpiar el HTML, usamos BeautifulSoup
        if clean_html and body_html:
            soup = BeautifulSoup(body_html, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        
        return body_html

    def update_complementary_products(self, product_id, complementary_product_id):
        """
        Update complementary products metafield
        """
        # First, check if the metafield exists
        existing_metafield = self.read_actual_complementary_products(product_id)
        gid_complementary_product_id = f"gid://shopify/Product/{complementary_product_id}"
        
        if existing_metafield:
            # Update existing metafield
            existing_values = json.loads(existing_metafield["value"])
            if gid_complementary_product_id not in existing_values:
                existing_values.append(gid_complementary_product_id)
                
                mutation = """
                mutation UpdateMetafield($input: MetafieldInput!) {
                  metafieldUpdate(input: $input) {
                    metafield {
                      id
                    }
                    userErrors {
                      field
                      message
                    }
                  }
                }
                """
                
                variables = {
                    "input": {
                        "id": f"gid://shopify/Metafield/{existing_metafield['id']}",
                        "value": json.dumps(existing_values),
                        "type": "list.product_reference"
                    }
                }
                
                result = self.execute_graphql(mutation, variables)
                
                if "errors" in result or result["data"]["metafieldUpdate"]["userErrors"]:
                    errors = result.get("errors") or result["data"]["metafieldUpdate"]["userErrors"]
                    print(f"Failed to update complementary product: {errors}")
        else:
            # Create new metafield
            mutation = """
            mutation CreateMetafield($input: MetafieldInput!) {
              metafieldCreate(input: $input) {
                metafield {
                  id
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "input": {
                    "parentResource": f"gid://shopify/Product/{product_id}",
                    "namespace": "shopify--discovery--product_recommendation",
                    "key": "complementary_products",
                    "value": json.dumps([gid_complementary_product_id]),
                    "type": "list.product_reference"
                }
            }
            
            result = self.execute_graphql(mutation, variables)
            
            if "errors" in result or result["data"]["metafieldCreate"]["userErrors"]:
                errors = result.get("errors") or result["data"]["metafieldCreate"]["userErrors"]
                print(f"Failed to create complementary product metafield: {errors}")

    def update_image_seo(self, product_id, image_id, new_alt):
        """
        Update image alt text (SEO)
        """
        mutation = """
        mutation UpdateProductImage($input: ProductImageUpdateInput!) {
          productImageUpdate(input: $input) {
            image {
              id
              altText
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/ProductImage/{image_id}",
                "altText": new_alt
            }
        }
        
        result = self.execute_graphql(mutation, variables)
        
        if "errors" in result or result["data"]["productImageUpdate"]["userErrors"]:
            errors = result.get("errors") or result["data"]["productImageUpdate"]["userErrors"]
            print(f"{image_id} image updating was failed: {errors}")
        else:
            print(f"{image_id} image was updated")

    def update_stock(self, inventory_item_id, new_stock, sku):
        """
        Update inventory level for a product variant
        """
        location_id = self.read_location_id(inventory_item_id)
        
        if location_id:
            mutation = """
            mutation AdjustInventoryLevel($input: InventoryAdjustQuantityInput!) {
              inventoryAdjustQuantity(input: $input) {
                inventoryLevel {
                  available
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "input": {
                    "inventoryItemId": f"gid://shopify/InventoryItem/{inventory_item_id}",
                    "locationId": f"gid://shopify/Location/{location_id}",
                    "availableDelta": new_stock  # Delta is the difference to adjust
                }
            }
            
            result = self.execute_graphql(mutation, variables)
            
            if "errors" in result or result["data"]["inventoryAdjustQuantity"]["userErrors"]:
                errors = result.get("errors") or result["data"]["inventoryAdjustQuantity"]["userErrors"]
                print(f"Error al actualizar stock para SKU {sku}: {errors}")
            else:
                print(f"Stock actualizado para SKU {sku}.")
        else:
            print(f"No se pudo obtener el location_id para inventory_item_id {inventory_item_id}")
        
        # Espera para evitar saturar la API o violar los límites de la tasa de solicitud
        time.sleep(1)

    def update_price(self, variant_id, new_price, sku):
        """
        Update variant price
        """
        mutation = """
        mutation UpdateProductVariant($input: ProductVariantInput!) {
          productVariantUpdate(input: $input) {
            productVariant {
              id
              price
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/ProductVariant/{variant_id}",
                "price": str(new_price)
            }
        }
        
        result = self.execute_graphql(mutation, variables)
        
        if "errors" in result or result["data"]["productVariantUpdate"]["userErrors"]:
            errors = result.get("errors") or result["data"]["productVariantUpdate"]["userErrors"]
            print(f"Error al actualizar el precio para el {sku}: {errors}")
        else:
            print(f"Precio actualizado para el sku {sku}")
        
        # Pausa después de cada actualización
        print("durmiendo...")
        time.sleep(1)
    
    def update_price_comparison(self, variant_id, compare_at_price, sku):
        """
        Update variant compare-at price
        """
        mutation = """
        mutation UpdateProductVariant($input: ProductVariantInput!) {
          productVariantUpdate(input: $input) {
            productVariant {
              id
              compareAtPrice
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/ProductVariant/{variant_id}",
                "compareAtPrice": str(compare_at_price)
            }
        }
        
        result = self.execute_graphql(mutation, variables)
        
        if "errors" in result or result["data"]["productVariantUpdate"]["userErrors"]:
            errors = result.get("errors") or result["data"]["productVariantUpdate"]["userErrors"]
            print(f"Error al actualizar el precio de comparación para el {sku}: {errors}")
        else:
            print(f"Precio de comparación actualizado para el sku {sku}")
        
        print("durmiendo...")
        time.sleep(1)

    def delete_complementary_products(self, product_id):
        """
        Delete complementary products metafield
        """
        existing_metafield = self.read_actual_complementary_products(product_id)
        
        if existing_metafield:
            mutation = """
            mutation DeleteMetafield($input: MetafieldDeleteInput!) {
              metafieldDelete(input: $input) {
                deletedId
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "input": {
                    "id": f"gid://shopify/Metafield/{existing_metafield['id']}"
                }
            }
            
            result = self.execute_graphql(mutation, variables)
            
            if "errors" in result or result["data"]["metafieldDelete"]["userErrors"]:
                errors = result.get("errors") or result["data"]["metafieldDelete"]["userErrors"]
                print(f"Failed to delete complementary products for product {product_id}: {errors}")
        else:
            print(f"No complementary products metafield found for product {product_id}")

    def search_products(self, search_terms, limit_per_term=10, fields=None):
        """
        Busca productos utilizando el motor de búsqueda de Shopify para múltiples términos.
        
        Args:
            search_terms (list): Lista de términos de búsqueda (ej. ["aceite de almendras", "esencia de coco"])
            limit_per_term (int): Número máximo de resultados a devolver por término
            fields (list): Lista de campos adicionales a retornar para cada producto
            
        Returns:
            dict: Diccionario con los términos de búsqueda como claves y listas de productos como valores
        """
        if not fields:
            fields = """
                id
                title
                handle
                vendor
                productType
                tags
                status
                createdAt
                updatedAt
                publishedAt
                descriptionHtml
                priceRangeV2 {
                    minVariantPrice {
                        amount
                        currencyCode
                    }
                    maxVariantPrice {
                        amount
                        currencyCode
                    }
                }
                images(first: 1) {
                    edges {
                        node {
                            id
                            url
                            altText
                        }
                    }
                }
                variants(first: 10) {
                    edges {
                        node {
                            id
                            title
                            sku
                            price
                            compareAtPrice
                            inventoryQuantity
                            selectedOptions {
                                name
                                value
                            }
                        }
                    }
                }
            """
        
        query = """
        query SearchProducts($query: String!, $limit: Int!) {
            products(query: $query, first: $limit) {
                edges {
                    node {
                        %s
                    }
                }
            }
        }
        """ % fields
        
        results = {}
        
        for term in search_terms:
            variables = {
                "query": term,
                "limit": limit_per_term
            }
            
            result = self.execute_graphql(query, variables)
            
            if "errors" in result:
                print(f"Error en búsqueda para '{term}': {result['errors']}")
                results[term] = []
                continue
                
            # Procesar resultados para este término
            term_results = []
            for edge in result["data"]["products"]["edges"]:
                product = edge["node"]
                
                # Convertir IDs y estructura a formato compatible con REST
                processed_product = {
                    "id": self._extract_id_from_gid(product["id"]),
                    "title": product["title"],
                    "handle": product["handle"],
                    "vendor": product["vendor"],
                    "product_type": product["productType"],
                    "tags": product["tags"],
                    "status": product["status"],
                    "created_at": product["createdAt"],
                    "updated_at": product["updatedAt"],
                    "published_at": product["publishedAt"],
                    "body_html": product["descriptionHtml"],
                }
                
                # Procesar rango de precios
                if "priceRangeV2" in product:
                    processed_product["price_min"] = product["priceRangeV2"]["minVariantPrice"]["amount"]
                    processed_product["price_max"] = product["priceRangeV2"]["maxVariantPrice"]["amount"]
                    processed_product["currency"] = product["priceRangeV2"]["minVariantPrice"]["currencyCode"]
                
                # Procesar imágenes
                processed_product["images"] = []
                if "images" in product and product["images"]["edges"]:
                    for image_edge in product["images"]["edges"]:
                        image = image_edge["node"]
                        processed_product["images"].append({
                            "id": self._extract_id_from_gid(image["id"]),
                            "src": image["url"],
                            "alt": image["altText"]
                        })
                
                # Procesar variantes
                processed_product["variants"] = []
                if "variants" in product:
                    for variant_edge in product["variants"]["edges"]:
                        variant = variant_edge["node"]
                        processed_variant = {
                            "id": self._extract_id_from_gid(variant["id"]),
                            "title": variant["title"],
                            "sku": variant["sku"],
                            "price": variant["price"],
                            "compare_at_price": variant["compareAtPrice"],
                            "inventory_quantity": variant["inventoryQuantity"],
                        }
                        
                        # Procesar opciones seleccionadas
                        if "selectedOptions" in variant:
                            for option in variant["selectedOptions"]:
                                option_name = option["name"].lower().replace(" ", "_")
                                processed_variant[option_name] = option["value"]
                        
                        processed_product["variants"].append(processed_variant)
                
                term_results.append(processed_product)
            
            # Guardar resultados para este término
            results[term] = term_results
            
        return results

    def search_products_consolidated(self, search_terms, limit_per_term=5, fields=None):
        """
        Busca productos utilizando múltiples términos y devuelve una lista simplificada
        solo con productos disponibles (status=ACTIVE) y los campos esenciales.
        
        Args:
            search_terms (list): Lista de términos de búsqueda
            limit_per_term (int): Número máximo de resultados por término
            fields (list): Lista de campos adicionales a retornar
            
        Returns:
            list: Lista simplificada de productos activos con sus variantes
        """
        results_by_term = self.search_products(search_terms, limit_per_term, fields)
        
        # Lista final de productos simplificados
        simplified_products = []
        
        # Conjunto para controlar duplicados
        product_ids_processed = set()
        
        for term, products in results_by_term.items():
            for product in products:
                # Solo incluir productos activos
                if product["status"] != "ACTIVE":
                    continue
                    
                product_id = product["id"]
                
                # Evitar duplicados
                if product_id in product_ids_processed:
                    continue
                    
                product_ids_processed.add(product_id)
                
                # Procesar cada variante como una línea individual
                if product.get("variants"):
                    for variant in product["variants"]:
                        # Crear estructura simplificada
                        simplified_product = {
                            "id": product["id"],
                            "title": product["title"],
                            "variant_id": variant["id"],
                            "variant_title": variant["title"],
                            "variant_sku": variant["sku"],
                            "variant_inventory_quantity": variant.get("inventory_quantity", 0),
                            "variant_price": variant.get("price", "0"),
                            #"matching_terms": [t for t in search_terms if t in term]
                        }
                        
                        # Añadir imagen principal si existe (fácil de extender)
                        #if product.get("images") and len(product["images"]) > 0:
                        #    simplified_product["image_src"] = product["images"][0].get("src", "")
                        
                        simplified_products.append(simplified_product)
                else:
                    # Para productos sin variantes, usar los valores del producto principal
                    simplified_product = {
                        "id": product["id"],
                        "title": product["title"],
                        "variant_id": product["id"],  # Usamos el ID del producto como ID de variante
                        "variant_title": "",
                        "variant_sku": product.get("sku", ""),  # Usar el SKU del producto principal
                        "variant_inventory_quantity": product.get("inventory_quantity", 0),
                        "variant_price": product.get("price_min", "0"),
                        #"matching_terms": [t for t in search_terms if t in term]
                    }
                    
                    # Añadir imagen principal si existe
                    #if product.get("images") and len(product["images"]) > 0:
                    #    simplified_product["image_src"] = product["images"][0].get("src", "")
                    
                    simplified_products.append(simplified_product)
        
        return simplified_products

# AUXILIAR

    def _extract_id_from_gid(self, gid):
        """
        Extract numeric ID from Shopify's GraphQL global ID
        Example: gid://shopify/Product/1234567890 -> 1234567890
        """
        if not gid:
            return None
            
        parts = gid.split('/')
        return parts[-1] if parts else None

    def export_products_to_json(self, products, path):
        """
        Export products to JSON file
        """
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(products, file, ensure_ascii=False, indent=4)
    
    def map_sku_to_product_id(self):
        """
        Método provisional para evitar errores - implementar correctamente
        """
        try:
            # Intentar usar la versión GraphQL
            return self._map_sku_to_product_id_graphql()
        except Exception as e:
            print(f"Error al mapear SKUs con GraphQL: {e}")
            # Retornar un diccionario vacío como fallback
            return {}
    
    def _map_sku_to_product_id_graphql(self):
        """
        Versión GraphQL de map_sku_to_product_id
        """
        sku_to_product_id = {}
        
        query = """
        query GetAllProductVariants($cursor: String) {
          productVariants(first: 250, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                sku
                product {
                  id
                }
              }
            }
          }
        }
        """
        
        variables = {"cursor": None}
        has_next_page = True
        
        while has_next_page:
            result = self.execute_graphql(query, variables)
            
            if "errors" in result:
                print(f"Error al obtener variantes: {result['errors']}")
                break
            
            variants_data = result["data"]["productVariants"]
            
            for edge in variants_data["edges"]:
                variant = edge["node"]
                sku = variant.get("sku")
                if sku:
                    product_id = self._extract_id_from_gid(variant["product"]["id"])
                    sku_to_product_id[sku] = product_id
            
            # Verificar paginación
            page_info = variants_data["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            if has_next_page:
                variables["cursor"] = page_info["endCursor"]
        
        return sku_to_product_id