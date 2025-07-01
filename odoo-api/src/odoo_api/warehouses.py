from .api import OdooAPI
import pandas as pd
from pprint import pprint

class OdooWarehouse(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    def get_stock_by_sku(self, sku):
        """
        Obtiene información de stock para un producto específico por SKU.
        Versión optimizada que consulta directamente por SKU sin obtener todo el inventario.
        
        Args:
            sku (str): SKU del producto a consultar
            
        Returns:
            dict: Información de stock consolidada
                {
                    "qty_available": float,
                    "virtual_available": float,
                    "locations": [
                        {"location": str, "warehouse": str, "quantity": float},
                        ...
                    ],
                    "product_name": str,
                    "sku": str,
                    "found": bool
                }
        """
        try:
            print(f"[DEBUG] Buscando producto con SKU: {sku}")
            # 1. Buscar el producto por SKU para obtener su ID
            product_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'search',
                [[['default_code', '=', sku]]]
            )
            
            print(f"[DEBUG] Product IDs encontrados: {product_ids}")
            if not product_ids:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": None,
                    "sku": sku,
                    "found": False
                }
            
            product_id = product_ids[0]
            print(f"[DEBUG] Using Product ID: {product_id}")
            
            # 2. Obtener información del producto
            product_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'read',
                [product_id], {'fields': ['name', 'default_code', 'product_template_attribute_value_ids']}
            )
            
            product_name = product_data['name']
            print(f"[DEBUG] Product name: {product_name}")
            
            # 3. Obtener atributos de variante si existen
            attribute_values = []
            if product_data['product_template_attribute_value_ids']:
                attribute_value_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'product.template.attribute.value', 'read',
                    [product_data['product_template_attribute_value_ids']], {'fields': ['name']}
                )
                attribute_values = [attr['name'] for attr in attribute_value_data]
            
            # Construir nombre completo del producto con atributos
            if attribute_values:
                product_name_with_attributes = product_name + ' - ' + ', '.join(attribute_values)
            else:
                product_name_with_attributes = product_name
            
            # 4. Obtener quants (stock) directamente para este producto
            stock_quants = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.quant', 'search_read',
                [[['product_id', '=', product_id]]],
                {'fields': ['quantity', 'location_id', 'reserved_quantity']}
            )
            
            print(f"[DEBUG] Stock quants encontrados: {len(stock_quants)}")
            
            if not stock_quants:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": product_name_with_attributes,
                    "sku": sku,
                    "found": True
                }
            
            # 5. Obtener información de ubicaciones que tienen quants
            location_ids = [quant['location_id'][0] for quant in stock_quants]
            
            # Obtener todas las ubicaciones (para posteriormente filtrar por tipo)
            all_locations = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.location', 'search_read',
                [[['id', 'in', location_ids]]],
                {'fields': ['id', 'name', 'usage', 'location_id']}
            )
            
            print(f"[DEBUG] Ubicaciones encontradas: {len(all_locations)}")
            
            if not all_locations:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": product_name_with_attributes,
                    "sku": sku,
                    "found": True
                }
            
            # 6. Obtener información de bodegas
            warehouse_ids = self.models.execute_kw(
                self.db, self.uid, self.password, 
                'stock.warehouse', 'search', [[]]
            )
            warehouses = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.warehouse', 'read', 
                [warehouse_ids, ['id', 'name', 'lot_stock_id']]
            )
            
            # Crear diccionario para mapear ubicaciones a bodegas
            warehouse_dict = {warehouse['lot_stock_id'][0]: warehouse['name'] for warehouse in warehouses}
            location_dict = {loc['id']: loc for loc in all_locations}
            
            # 7. Calcular stock disponible (como lo hace Odoo: quantity - reserved_quantity en ubicaciones internas)
            locations_with_stock = []
            total_qty_available = 0
            total_qty_virtual = 0
            
            for quant in stock_quants:
                location_id = quant['location_id'][0]
                quantity = quant['quantity']
                reserved_quantity = quant['reserved_quantity']
                available_quantity = quantity - reserved_quantity
                
                location_data = location_dict.get(location_id)
                if not location_data:
                    continue
                    
                # Solo considerar ubicaciones internas para stock disponible (como hace Odoo)
                if location_data['usage'] == 'internal' and quantity > 0:
                    location_name = location_data['name']
                    
                    # Determinar bodega
                    parent_location_id = location_data['location_id'][0] if location_data['location_id'] else None
                    warehouse_name = warehouse_dict.get(parent_location_id, '')
                    
                    # Construir nombre completo de ubicación
                    if location_name == 'Stock' and parent_location_id:
                        full_location_name = location_data['location_id'][1] + '/' + location_name
                    else:
                        full_location_name = location_name
                    
                    if warehouse_name and not full_location_name.startswith(warehouse_name):
                        full_location_name = f"{warehouse_name}/{full_location_name}"
                    
                    locations_with_stock.append({
                        "location": full_location_name,
                        "warehouse": warehouse_name,
                        "quantity": quantity,
                        "reserved": reserved_quantity,
                        "available": available_quantity
                    })
                    
                    total_qty_available += available_quantity
                
                # Para virtual, incluir todas las ubicaciones (positivas y negativas)
                total_qty_virtual += quantity
            
            print(f"[DEBUG] Total disponible calculado: {total_qty_available}")
            print(f"[DEBUG] Ubicaciones con stock: {len(locations_with_stock)}")
            
            return {
                "qty_available": total_qty_available,
                "virtual_available": total_qty_virtual,
                "locations": locations_with_stock,
                "product_name": product_name_with_attributes,
                "sku": sku,
                "found": True
            }
            
        except Exception as e:
            print(f"[ERROR] Error en get_stock_by_sku: {str(e)}")
            return {
                "qty_available": 0,
                "virtual_available": 0,
                "locations": [],
                "product_name": None,
                "sku": sku,
                "found": False,
                "error": str(e)
            }

    def read_stock_by_location(self):
        # Obtener todas las ubicaciones que son del tipo 'Ubicación interna' en una sola llamada
        locations = self.models.execute_kw(self.db, self.uid, self.password,
            'stock.location', 'search_read', [[['usage', '=', 'internal']]], {'fields': ['id', 'name', 'location_id']})
        # Obtener todas las bodegas
        warehouse_ids = self.models.execute_kw(self.db, self.uid, self.password, 'stock.warehouse', 'search', [[]])
        warehouses = self.models.execute_kw(self.db, self.uid, self.password,
            'stock.warehouse', 'read', [warehouse_ids, ['id', 'name', 'lot_stock_id']])
        # Crear un diccionario para mapear ubicaciones raíz (lot_stock_id) a bodegas
        warehouse_dict = {warehouse['lot_stock_id'][0]: warehouse['name'] for warehouse in warehouses}
        # Consultar los inventarios por SKU para cada ubicación en una sola llamada
        inventory_data = []
        location_ids = [location['id'] for location in locations]  # Extraer todos los IDs de las ubicaciones
        # Obtener todos los stock quants en una sola llamada para todas las ubicaciones
        stock_quants = self.models.execute_kw(self.db, self.uid, self.password,
            'stock.quant', 'search_read', [[['location_id', 'in', location_ids]]], 
            {'fields': ['product_id', 'quantity', 'location_id']})

        # Extraer los product_ids para hacer una sola llamada a 'product.product'
        product_ids = list(set([stock_quant['product_id'][0] for stock_quant in stock_quants]))

        # Obtener todos los productos en una sola llamada
        products = self.models.execute_kw(self.db, self.uid, self.password,
            'product.product', 'read', [product_ids, ['default_code', 'name', 'product_template_attribute_value_ids', 'product_tag_ids']])

        # Crear un diccionario para mapear product_id a sus datos
        product_dict = {product['id']: product for product in products}

        # Obtener los tags de los productos en una sola llamada
        all_tag_ids = list(set([tag_id for product in products for tag_id in product['product_tag_ids']]))
        tag_dict = {}
        if all_tag_ids:
            tags = self.models.execute_kw(self.db, self.uid, self.password,
                'product.tag', 'read', [all_tag_ids, ['name']])
            tag_dict = {tag['id']: tag['name'] for tag in tags}

        # Procesar los stock quants y formar los datos finales
        for stock_quant in stock_quants:
            product_data = product_dict[stock_quant['product_id'][0]]
            product_name_with_attributes = product_data['name']

            # Obtener los atributos de la variante si existen
            attribute_values = []
            if product_data['product_template_attribute_value_ids']:
                attribute_value_data = self.models.execute_kw(self.db, self.uid, self.password,
                    'product.template.attribute.value', 'read', [product_data['product_template_attribute_value_ids'], ['name']])
                attribute_values = [attr['name'] for attr in attribute_value_data]

            if attribute_values:
                product_name_with_attributes += ' - ' + ', '.join(attribute_values)

            # Obtener los tags del producto
            product_tags = [tag_dict.get(tag_id, '') for tag_id in product_data['product_tag_ids']]

            # Obtener el nombre de la ubicación
            location_data = next((loc for loc in locations if loc['id'] == stock_quant['location_id'][0]), None)
            location_name = location_data['name'] if location_data else ''

            # Obtener el nombre completo de la bodega solo si la ubicación no es la raíz de la bodega
            parent_location_id = location_data['location_id'][0] if location_data and location_data['location_id'] else None
            warehouse_name = warehouse_dict.get(parent_location_id, '')

            # Si la ubicación es "Stock" pero pertenece a una jerarquía mayor (como "FV/Stock"), construimos el nombre completo
            if location_name == 'Stock' and parent_location_id:
                location_name = location_data['location_id'][1] + '/' + location_name

            # Evitar agregar el nombre de la bodega si ya está presente en la ubicación
            if warehouse_name and not location_name.startswith(warehouse_name):
                full_location_name = f"{warehouse_name}/{location_name}"
            else:
                full_location_name = location_name

            # Agregar los datos al inventario
            inventory_data.append({
                'warehouse': warehouse_name,  # Nombre de la bodega
                'location': full_location_name,  # Nombre completo de la ubicación
                'product_id': product_name_with_attributes,  # Nombre del producto con la variante
                'internal_reference': product_data.get('default_code', ''),  # Referencia interna
                'quantity': stock_quant['quantity'],
                'tags': ', '.join(product_tags)  # Nombres de los tags
            })

        # Convertir a DataFrame para un manejo más sencillo
        df_inventory = pd.DataFrame(inventory_data)

        return df_inventory