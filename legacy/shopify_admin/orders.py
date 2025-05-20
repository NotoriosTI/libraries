import re
from .api_shopify_admin import ShopifyAdminAPI
import pandas as pd
import requests
import json

class ShopifyOrders(ShopifyAdminAPI):
    def __init__(self, shop_url=None, api_password=None, api_version=None):
        super().__init__(shop_url, api_password, api_version)
        
        if not hasattr(self, "execute_graphql"):
            print("ADVERTENCIA: execute_graphql no encontrado en la instancia, definiendo manualmente")
            self.execute_graphql = self._execute_graphql_fallback
    
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


    def create_checkout_permalink(self, products_data, email, phone):
        """
        Crea un permalink de checkout de Shopify para añadir productos al carrito.
        
        Args:
            products_data (list): Lista de productos con formato:
                [
                    {'variant_id': '12345678901234', 'quantity': 1},
                    {'variant_id': '98765432109876', 'quantity': 2}
                ]
            discount_code (str, opcional): Código de descuento para aplicar
            note (str, opcional): Nota para el carrito
                    
        Returns:
            str: Permalink para checkout directo
        """
        # Verificar que los productos están en formato correcto
        if not isinstance(products_data, list) or len(products_data) == 0:
            print("Error: products_data debe ser una lista no vacía de diccionarios")
            return None
            
        # Construir la base de la URL de checkout
        shop_domain = self._get_domain()
        
        permalink_parts = []
        
        for product in products_data:
            if not isinstance(product, dict) or 'variant_id' not in product or 'quantity' not in product:
                print(f"Error: Formato incorrecto de producto: {product}")
                continue
                
            variant_id = product['variant_id']
            quantity = product['quantity']
            
            permalink_parts.append(f"{variant_id}:{quantity}")
        
        # Construir la URL base
        if permalink_parts:
            permalink = f"{shop_domain}/cart/{':'.join(permalink_parts)}"
        else:
            print("Advertencia: No se añadieron productos al carrito")
            return None
        
        params = []
        
        if email:
            params.append(f"checkout[email]={email}")

        if params:
            permalink += f"?{'&'.join(params)}"
        
        return permalink

    def read_all_orders(self, limit=250, query=None):
        """
        Read all orders using GraphQL pagination
        
        Args:
            limit (int): Number of orders to fetch per page
            query (str): Optional query filter (e.g. "created_at:>2023-01-01")
            
        Returns:
            list: List of order objects
        """
        orders = []
        query_str = """
        query GetOrders($cursor: String, $limit: Int!, $query: String) {
          orders(first: $limit, after: $cursor, query: $query) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                name
                email
                phone
                createdAt
                displayFinancialStatus
                displayFulfillmentStatus
                note
                tags
                subtotalPrice
                totalPrice
                totalTax
                totalShippingPrice
                cancelledAt
                processedAt
                customer {
                  id
                  firstName
                  lastName
                  email
                  phone
                }
                shippingAddress {
                  address1
                  address2
                  city
                  province
                  country
                  zip
                  phone
                }
                lineItems(first: 100) {
                  edges {
                    node {
                      id
                      name
                      quantity
                      sku
                      originalUnitPrice
                      discountedUnitPrice
                      variant {
                        id
                        title
                        product {
                          id
                          title
                          handle
                        }
                      }
                    }
                  }
                }
                fulfillments {
                  id
                  createdAt
                  status
                  trackingInfo {
                    number
                    url
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "limit": limit,
            "cursor": None,
            "query": query
        }
        
        has_next_page = True
        
        while has_next_page:
            result = self.execute_graphql(query_str, variables)
            
            if "errors" in result:
                print(f"GraphQL Error: {result['errors']}")
                break
                
            order_data = result["data"]["orders"]
            
            # Extract orders from edges
            for edge in order_data["edges"]:
                node = edge["node"]
                # Convert GraphQL ID format to numeric ID
                node["id"] = self._extract_id_from_gid(node["id"])
                
                # Process customer data
                if node.get("customer") and node["customer"]:
                    node["customer"]["id"] = self._extract_id_from_gid(node["customer"]["id"])
                
                # Process line items
                line_items = []
                for line_item_edge in node["lineItems"]["edges"]:
                    line_item = line_item_edge["node"]
                    line_item["id"] = self._extract_id_from_gid(line_item["id"])
                    
                    # Process variant and product
                    if line_item.get("variant") and line_item["variant"]:
                        line_item["variant_id"] = self._extract_id_from_gid(line_item["variant"]["id"])
                        if line_item["variant"].get("product") and line_item["variant"]["product"]:
                            line_item["product_id"] = self._extract_id_from_gid(line_item["variant"]["product"]["id"])
                            line_item["product_title"] = line_item["variant"]["product"]["title"]
                            line_item["product_handle"] = line_item["variant"]["product"]["handle"]
                        
                    line_items.append(line_item)
                
                # Replace line items structure with simpler list
                node["line_items"] = line_items
                
                # Process fulfillments
                if node.get("fulfillments"):
                    for fulfillment in node["fulfillments"]:
                        fulfillment["id"] = self._extract_id_from_gid(fulfillment["id"])
                
                # Update standard keys for compatibility
                node["financial_status"] = node["displayFinancialStatus"]
                node["fulfillment_status"] = node["displayFulfillmentStatus"]
                node["created_at"] = node["createdAt"]
                node["processed_at"] = node["processedAt"]
                node["cancelled_at"] = node["cancelledAt"]
                node["subtotal_price"] = node["subtotalPrice"]
                node["total_price"] = node["totalPrice"]
                node["total_tax"] = node["totalTax"]
                node["total_shipping_price"] = node["totalShippingPrice"]
                
                orders.append(node)
            
            # Check if there's another page
            page_info = order_data["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            
            if has_next_page:
                variables["cursor"] = page_info["endCursor"]
            
        return orders

    def read_order_by_id(self, order_id):
        """
        Read a specific order by its ID
        
        Args:
            order_id (str): The order ID to fetch
            
        Returns:
            dict: Order details
        """
        query = """
        query GetOrder($orderId: ID!) {
          order(id: $orderId) {
            id
            name
            email
            phone
            createdAt
            displayFinancialStatus
            displayFulfillmentStatus
            note
            tags
            subtotalPrice
            totalPrice
            totalTax
            totalShippingPrice
            cancelledAt
            processedAt
            customer {
              id
              firstName
              lastName
              email
              phone
            }
            shippingAddress {
              address1
              address2
              city
              province
              country
              zip
              phone
            }
            lineItems(first: 100) {
              edges {
                node {
                  id
                  name
                  quantity
                  sku
                  originalUnitPrice
                  discountedUnitPrice
                  variant {
                    id
                    title
                    product {
                      id
                      title
                      handle
                    }
                  }
                }
              }
            }
            fulfillments {
              id
              createdAt
              status
              trackingInfo {
                number
                url
              }
            }
          }
        }
        """
        
        variables = {
            "orderId": f"gid://shopify/Order/{order_id}"
        }
        
        result = self.execute_graphql(query, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return None
        
        order = result["data"]["order"]
        if not order:
            return None
            
        # Convert GraphQL ID format to numeric ID
        order["id"] = self._extract_id_from_gid(order["id"])
        
        # Process customer data
        if order.get("customer") and order["customer"]:
            order["customer"]["id"] = self._extract_id_from_gid(order["customer"]["id"])
        
        # Process line items
        line_items = []
        for line_item_edge in order["lineItems"]["edges"]:
            line_item = line_item_edge["node"]
            line_item["id"] = self._extract_id_from_gid(line_item["id"])
            
            # Process variant and product
            if line_item.get("variant") and line_item["variant"]:
                line_item["variant_id"] = self._extract_id_from_gid(line_item["variant"]["id"])
                if line_item["variant"].get("product") and line_item["variant"]["product"]:
                    line_item["product_id"] = self._extract_id_from_gid(line_item["variant"]["product"]["id"])
                    line_item["product_title"] = line_item["variant"]["product"]["title"]
                    line_item["product_handle"] = line_item["variant"]["product"]["handle"]
                
            line_items.append(line_item)
        
        # Replace line items structure with simpler list
        order["line_items"] = line_items
        
        # Process fulfillments
        if order.get("fulfillments"):
            for fulfillment in order["fulfillments"]:
                fulfillment["id"] = self._extract_id_from_gid(fulfillment["id"])
        
        # Update standard keys for compatibility
        order["financial_status"] = order["displayFinancialStatus"]
        order["fulfillment_status"] = order["displayFulfillmentStatus"]
        order["created_at"] = order["createdAt"]
        order["processed_at"] = order["processedAt"]
        order["cancelled_at"] = order["cancelledAt"]
        order["subtotal_price"] = order["subtotalPrice"]
        order["total_price"] = order["totalPrice"]
        order["total_tax"] = order["totalTax"]
        order["total_shipping_price"] = order["totalShippingPrice"]
            
        return order

    def read_order_by_number(self, order_number):
        order_number = re.sub(r'[^0-9]', '', order_number.lower())

        query = """
        query GetOrderByNumber($query: String!) {
        orders(first: 1, query: $query) {
            edges {
            node {
                id
                name
                email
                phone
                createdAt
                updatedAt
                displayFinancialStatus
                displayFulfillmentStatus
                note
                tags
                subtotalPrice
                totalPrice
                totalTax
                totalShippingPrice
                cancelledAt
                processedAt
                customer {
                    id
                    firstName
                    lastName
                    email
                    phone
                }
                shippingAddress {
                    address1
                    address2
                    city
                    province
                    country
                    zip
                    phone
                    name
                }
                shippingLines(first: 10) {
                    edges {
                        node {
                        title
                        code
                        source
                        }
                    }
                }
                lineItems(first: 100) {
                    edges {
                        node {
                        id
                        name
                        quantity
                        sku
                        requiresShipping
                        fulfillableQuantity
                        variant {
                            id
                            title
                            sku
                            product {
                            id
                            title
                            handle
                            }
                        }
                        }
                    }
                }
                fulfillments {
                    id
                    createdAt
                    status
                    displayStatus
                    trackingInfo {
                        number
                        url
                        company
                    }
                }
                metafields(first: 50) {
                    edges {
                        node {
                        namespace
                        key
                        value
                        }
                    }
                }
            }
            }
        }
        }
        """

        variables = {"query": f"name:{order_number}"}

        result = self.execute_graphql(query, variables)

        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return None

        order_edges = result["data"]["orders"]["edges"]
        if not order_edges:
            return None

        order = order_edges[0]["node"]

        order["id"] = self._extract_id_from_gid(order["id"])

        if order.get("customer"):
            order["customer"]["id"] = self._extract_id_from_gid(order["customer"]["id"])

        line_items = []
        for line_item_edge in order["lineItems"]["edges"]:
            item = line_item_edge["node"]
            item["id"] = self._extract_id_from_gid(item["id"])

            if item.get("variant"):
                item["variant_id"] = self._extract_id_from_gid(item["variant"]["id"])
                if item["variant"].get("product"):
                    item["product_id"] = self._extract_id_from_gid(item["variant"]["product"]["id"])
                    item["product_title"] = item["variant"]["product"]["title"]
                    item["product_handle"] = item["variant"]["product"]["handle"]
            line_items.append(item)

        order["line_items"] = line_items

        shipping_lines = []
        for shipping_edge in order["shippingLines"]["edges"]:
            shipping = shipping_edge["node"]
            shipping_lines.append(shipping)

        order["shipping_lines"] = shipping_lines

        fulfillments = []
        for fulfillment in order.get("fulfillments", []):
            fulfillment["id"] = self._extract_id_from_gid(fulfillment["id"])
            fulfillments.append(fulfillment)

        order["fulfillments"] = fulfillments

        metafields = []
        for metafield_edge in order["metafields"]["edges"]:
            metafield = metafield_edge["node"]
            metafields.append({
                "namespace": metafield["namespace"],
                "key": metafield["key"],
                "value": metafield["value"]
            })

        order["metafields"] = metafields

        order.update({
            "financial_status": order["displayFinancialStatus"],
            "fulfillment_status": order["displayFulfillmentStatus"],
            "created_at": order["createdAt"],
            "updated_at": order["updatedAt"],
            "processed_at": order["processedAt"],
            "cancelled_at": order["cancelledAt"],
            "subtotal_price": order["subtotalPrice"],
            "total_price": order["totalPrice"],
            "total_tax": order["totalTax"],
            "total_shipping_price": order["totalShippingPrice"],
        })

        # Verificar si es un retiro en tienda antes de agregar fulfillment_orders
        is_pickup = False
        
        # Verificar en shipping_lines si es retiro en tienda
        for shipping in shipping_lines:
            # Verificar si el código o título contiene indicadores de retiro en tienda
            if (shipping.get("code") and "pickup" in shipping.get("code").lower()) or \
            (shipping.get("title") and any(term in shipping.get("title").lower() 
                                            for term in ["pickup", "retiro", "tienda"])):
                is_pickup = True
                break
        
        # También podemos verificar en los tags si contiene alguna referencia a retiro en tienda
        if not is_pickup and order.get("tags"):
            tags = order.get("tags")
            if isinstance(tags, list):
                pickup_tags = ["pickup", "retiro", "tienda"]
                if any(any(tag in t.lower() for tag in pickup_tags) for t in tags):
                    is_pickup = True
            elif isinstance(tags, str):
                pickup_tags = ["pickup", "retiro", "tienda"]
                if any(tag in tags.lower() for tag in pickup_tags):
                    is_pickup = True

        # Solo agregar fulfillment_orders si es un retiro en tienda
        if is_pickup:
            fulfillment_orders = self.read_fulfillment_orders_status(order["id"])
            
            pickup_status = "Desconocido"
            if fulfillment_orders:
                fulfillment = fulfillment_orders[0]
                status = fulfillment["status"]
                supported_actions = fulfillment["supported_actions"]

                if status == "IN_PROGRESS" and not supported_actions:
                    pickup_status = "Listo para retiro"
                elif status == "OPEN":
                    pickup_status = "No preparado"

            order["pickup_status_interpretado"] = pickup_status
            order["fulfillment_orders"] = fulfillment_orders

        return order


    def read_fulfillment_orders_status(self, order_id):
        query = """
        query fulfillmentOrders($orderId: ID!) {
        order(id: $orderId) {
            fulfillmentOrders(first: 5) {
            edges {
                node {
                id
                status
                requestStatus
                supportedActions {
                    action
                }
                deliveryMethod {
                    methodType
                }
                assignedLocation {
                    name
                }
                }
            }
            }
        }
        }
        """
        variables = {"orderId": f"gid://shopify/Order/{order_id}"}
        result = self.execute_graphql(query, variables)

        if "errors" in result:
            print("GraphQL Error:", result["errors"])
            return None

        fulfillment_orders = result["data"]["order"]["fulfillmentOrders"]["edges"]
        statuses = []
        for fulfillment in fulfillment_orders:
            node = fulfillment["node"]
            statuses.append({
                "fulfillment_order_id": self._extract_id_from_gid(node["id"]),
                "status": node["status"],
                "request_status": node["requestStatus"],
                "supported_actions": [action["action"] for action in node["supportedActions"]],
                "delivery_method": node["deliveryMethod"]["methodType"],
                "location": node["assignedLocation"]["name"],
            })

        return statuses

    def read_all_orders_in_dataframe(self, query=None):
        """
        Read all orders and convert to DataFrame
        
        Args:
            query (str): Optional query filter
            
        Returns:
            DataFrame: Pandas DataFrame with order data
        """
        orders = self.read_all_orders(query=query)
        
        # Flatten the line items to create rows
        order_rows = []
        for order in orders:
            # Base order info without line items
            base_order = {
                'id': order['id'],
                'name': order['name'],
                'email': order['email'],
                'phone': order.get('phone', ''),
                'created_at': order['created_at'],
                'financial_status': order['financial_status'],
                'fulfillment_status': order['fulfillment_status'],
                'note': order.get('note', ''),
                'tags': order.get('tags', ''),
                'subtotal_price': order['subtotal_price'],
                'total_price': order['total_price'],
                'total_tax': order['total_tax'],
                'total_shipping_price': order.get('total_shipping_price', '0'),
                'cancelled_at': order.get('cancelled_at', None),
                'processed_at': order.get('processed_at', None),
            }
            
            # Add customer data if available
            if 'customer' in order and order['customer']:
                base_order.update({
                    'customer_id': order['customer'].get('id', ''),
                    'customer_first_name': order['customer'].get('firstName', ''),
                    'customer_last_name': order['customer'].get('lastName', ''),
                    'customer_email': order['customer'].get('email', ''),
                    'customer_phone': order['customer'].get('phone', ''),
                })
            
            # Add shipping address if available
            if 'shippingAddress' in order and order['shippingAddress']:
                base_order.update({
                    'shipping_address1': order['shippingAddress'].get('address1', ''),
                    'shipping_address2': order['shippingAddress'].get('address2', ''),
                    'shipping_city': order['shippingAddress'].get('city', ''),
                    'shipping_province': order['shippingAddress'].get('province', ''),
                    'shipping_country': order['shippingAddress'].get('country', ''),
                    'shipping_zip': order['shippingAddress'].get('zip', ''),
                    'shipping_phone': order['shippingAddress'].get('phone', ''),
                })
            
            # Create a row for each line item
            for line_item in order.get('line_items', []):
                row = base_order.copy()
                row.update({
                    'line_item_id': line_item.get('id', ''),
                    'line_item_name': line_item.get('name', ''),
                    'line_item_quantity': line_item.get('quantity', 0),
                    'line_item_sku': line_item.get('sku', ''),
                    'line_item_price': line_item.get('originalUnitPrice', '0'),
                    'line_item_discounted_price': line_item.get('discountedUnitPrice', '0'),
                    'variant_id': line_item.get('variant_id', ''),
                    'product_id': line_item.get('product_id', ''),
                    'product_title': line_item.get('product_title', ''),
                    'product_handle': line_item.get('product_handle', ''),
                })
                order_rows.append(row)
            
            # If there are no line items, still add the order
            if not order.get('line_items'):
                order_rows.append(base_order)
        
        # Convert to DataFrame
        df_orders = pd.DataFrame(order_rows)
        
        return df_orders

    def update_order_tags(self, order_id, tags):
        """
        Update order tags
        
        Args:
            order_id (str): Order ID to update
            tags (list): New list of tags
            
        Returns:
            bool: True if successful, False otherwise
        """
        mutation = """
        mutation UpdateOrderTags($id: ID!, $tags: [String!]) {
          orderUpdate(input: {id: $id, tags: $tags}) {
            order {
              id
              tags
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "id": f"gid://shopify/Order/{order_id}",
            "tags": tags
        }
        
        result = self.execute_graphql(mutation, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return False
            
        user_errors = result["data"]["orderUpdate"]["userErrors"]
        if user_errors:
            print(f"Failed to update order tags: {user_errors}")
            return False
            
        return True

    def update_order_note(self, order_id, note):
        """
        Update order note
        
        Args:
            order_id (str): Order ID to update
            note (str): New note text
            
        Returns:
            bool: True if successful, False otherwise
        """
        mutation = """
        mutation UpdateOrderNote($id: ID!, $note: String!) {
          orderUpdate(input: {id: $id, note: $note}) {
            order {
              id
              note
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "id": f"gid://shopify/Order/{order_id}",
            "note": note
        }
        
        result = self.execute_graphql(mutation, variables)
        
        if "errors" in result:
            print(f"GraphQL Error: {result['errors']}")
            return False
            
        user_errors = result["data"]["orderUpdate"]["userErrors"]
        if user_errors:
            print(f"Failed to update order note: {user_errors}")
            return False
            
        return True

# AUXILIAR

    def _extract_id_from_gid(self, gid):
        """
        Extract numeric ID from Shopify's GraphQL global ID
        Example: gid://shopify/Order/1234567890 -> 1234567890
        """
        if not gid:
            return None
            
        parts = gid.split('/')
        return parts[-1] if parts else None

    def export_orders_to_json(self, orders, path):
        """
        Export orders to JSON file
        """
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(orders, file, ensure_ascii=False, indent=4)

    def _get_domain(self):
        """
        Obtiene el dominio al que redirecciona la tienda Shopify.
        
        Returns:
            str: URL de redirección si existe, o la URL original si no hay redirección
        """
        shop_domain = self.shop_url.rstrip('/')
        if not shop_domain.startswith('http'):
            shop_domain = f"https://{shop_domain}"
            
        try:
            # Realizar petición sin seguir redirecciones
            response = requests.get(shop_domain, allow_redirects=False, timeout=5)
            
            # Verificar si hay redirección
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('Location')
                
                # Extraer solo el dominio
                from urllib.parse import urlparse
                parsed_url = urlparse(redirect_url)
                redirect_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                return redirect_domain
            else:
                return shop_domain
        except Exception as e:
            print(f"Error al verificar redirección: {e}")
            return shop_domain

