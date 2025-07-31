from .api_shopify_storefront import StorefrontAPI

class StorefrontSearch(StorefrontAPI):
    def __init__(self, shop_url=None, storefront_access_token=None, api_version=None):
        super().__init__(shop_url, storefront_access_token, api_version)
    
    def search_products(self, search_terms, limit_per_term=10, fields=None):
        """
        Busca productos utilizando la API de Storefront para múltiples términos de búsqueda
        
        Args:
            search_terms (list): Lista de términos de búsqueda
            limit_per_term (int): Número máximo de resultados por término
            fields (str): Campos personalizados para incluir en la consulta
            
        Returns:
            dict: Un diccionario con términos de búsqueda como claves y listas de productos como valores
        """
        if not fields:
            fields = """
                id
                title
                handle
                vendor
                productType
                tags
                availableForSale
                createdAt
                updatedAt
                publishedAt
                description
                descriptionHtml
                priceRange {
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
                            price {
                                amount
                                currencyCode
                            }
                            compareAtPrice {
                                amount
                                currencyCode
                            }
                            quantityAvailable
                            selectedOptions {
                                name
                                value
                            }
                        }
                    }
                }
            """
        
        # La API de búsqueda de Storefront usa un endpoint genérico 'search'
        # Especificamos que solo queremos productos con 'types: PRODUCT'
        query = """
        query SearchProducts($query: String!, $limit: Int!) {
            search(query: $query, types: PRODUCT, first: $limit) {
                edges {
                    node {
                        ... on Product {
                            %s
                        }
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
                print(f"Error en la búsqueda de '{term}': {result['errors']}")
                results[term] = []
                continue
                
            # Procesar resultados para este término
            term_results = []
            for edge in result["data"]["search"]["edges"]:
                product = edge["node"]
                
                # Convertir IDs y estructura a formato compatible con REST
                processed_product = {
                    "id": self._extract_id_from_gid(product["id"]),
                    "title": product["title"],
                    "handle": product["handle"],
                    "vendor": product["vendor"],
                    "product_type": product["productType"],  # Mantener clave consistente con API REST
                    "tags": product["tags"],
                    "status": "ACTIVE" if product["availableForSale"] else "DRAFT",  # Convertir a formato Admin API
                    "created_at": product["createdAt"],
                    "updated_at": product["updatedAt"],
                    "published_at": product["publishedAt"],
                    "description": product["description"],
                    "body_html": product["descriptionHtml"],  # Consistente con API REST
                }
                
                # Procesar rango de precios
                if "priceRange" in product:
                    processed_product["price_min"] = product["priceRange"]["minVariantPrice"]["amount"]
                    processed_product["price_max"] = product["priceRange"]["maxVariantPrice"]["amount"]
                    processed_product["currency"] = product["priceRange"]["minVariantPrice"]["currencyCode"]
                
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
                            "price": variant["price"]["amount"],
                            "compareAtPrice": variant["compareAtPrice"]["amount"] if variant["compareAtPrice"] else None,  # Mantener consistencia con GraphQL Admin
                            "compare_at_price": variant["compareAtPrice"]["amount"] if variant["compareAtPrice"] else None,  # Mantener consistencia con REST
                            "inventoryQuantity": variant.get("quantityAvailable", 0),  # Consistente con GraphQL Admin
                            "inventory_quantity": variant.get("quantityAvailable", 0),  # Consistente con REST
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
        solo con productos disponibles (availableForSale=true) y los campos esenciales.
        
        Args:
            search_terms (list): Lista de términos de búsqueda
            limit_per_term (int): Número máximo de resultados por término
            fields (str): Campos personalizados para incluir en la consulta
            
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
                # Solo incluir productos activos (usando la clave status como en Admin API)
                if product.get("status") != "ACTIVE":
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
                        }
                        
                        simplified_products.append(simplified_product)
                else:
                    # Para productos sin variantes, usar los valores del producto principal
                    simplified_product = {
                        "id": product["id"],
                        "title": product["title"],
                        "variant_id": product["id"],  # Usar ID del producto como ID de variante
                        "variant_title": "",
                        "variant_sku": "",
                        "variant_inventory_quantity": 0,
                        "variant_price": product.get("price_min", "0"),
                    }
                    
                    simplified_products.append(simplified_product)
        
        return simplified_products

    def _extract_id_from_gid(self, gid):
        """
        Extrae el ID numérico del ID global de GraphQL de Shopify
        Ejemplo: gid://shopify/Product/1234567890 -> 1234567890
        """
        if not gid:
            return None
            
        parts = gid.split('/')
        return parts[-1] if parts else None