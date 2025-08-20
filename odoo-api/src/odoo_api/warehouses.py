from .api import OdooAPI
import pandas as pd
from pprint import pprint
from typing import List, Tuple
from config_manager import secrets

class OdooWarehouse(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    def get_stock_by_sku(self, sku):
        """
        Obtiene información de stock para un producto específico por SKU.
        Versión optimizada que consulta directamente por SKU sin obtener todo el inventario.
        
        Args:
            sku (str or list): SKU del producto a consultar o lista de SKUs para procesamiento batch
            
        Returns:
            dict: Información de stock consolidada (para un SKU) o dict de resultados (para múltiples SKUs)
        """
        # Detectar si es un SKU individual o una lista
        if isinstance(sku, str):
            return self._get_stock_single_sku(sku)
        elif isinstance(sku, list):
            # Validar lista vacía
            if len(sku) == 0:
                raise ValueError("La lista de SKUs no puede estar vacía")
            # Optimización: si la lista tiene un solo elemento, usar la función individual
            if len(sku) == 1:
                return self._get_stock_single_sku(sku[0])
            else:
                return self._get_stock_multiple_skus(sku)
        else:
            raise ValueError("El argumento 'sku' debe ser un string o una lista de strings")

    def _get_stock_single_sku(self, sku):
        """
        Procesa un solo SKU.
        """
        try:
            # 1. Buscar el producto por SKU para obtener su ID
            product_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'search',
                [[['default_code', '=', sku]]]
            )
            
            if not product_ids:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": None,
                    "sku": sku,
                    "found": False,
                    "uom": None
                }
            
            product_id = product_ids[0]
            
            # 2. Obtener información del producto
            product_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'read',
                [product_id], {'fields': ['name', 'default_code', 'product_template_attribute_value_ids', 'uom_id']}
            )
            
            # Manejar el caso donde product_data es una lista
            if isinstance(product_data, list) and len(product_data) > 0:
                product_info = product_data[0]
            else:
                product_info = product_data
            
            product_name = product_info['name']
            
            # 3. Obtener atributos de variante si existen
            attribute_values = []
            if product_info['product_template_attribute_value_ids']:
                attribute_value_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'product.template.attribute.value', 'read',
                    [product_info['product_template_attribute_value_ids']], {'fields': ['name']}
                )
                attribute_values = [attr['name'] for attr in attribute_value_data]
            
            # Construir nombre completo del producto con atributos
            if attribute_values:
                product_name_with_attributes = product_name + ' - ' + ', '.join(attribute_values)
            else:
                product_name_with_attributes = product_name
            
            # 4. Obtener información de UOM
            uom_name = None
            if product_info['uom_id']:
                uom_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'uom.uom', 'read',
                    [product_info['uom_id'][0]], {'fields': ['name']}
                )
                if uom_data:
                    uom_name = uom_data[0]['name']
            
            # 5. Obtener quants (stock) directamente para este producto
            stock_quants = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.quant', 'search_read',
                [[['product_id', '=', product_id]]],
                {'fields': ['quantity', 'location_id', 'reserved_quantity']}
            )
            
            if not stock_quants:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": product_name_with_attributes,
                    "sku": sku,
                    "found": True,
                    "uom": uom_name
                }
            
            # 6. Obtener información de ubicaciones que tienen quants
            location_ids = [quant['location_id'][0] for quant in stock_quants]
            
            # Obtener todas las ubicaciones (para posteriormente filtrar por tipo)
            all_locations = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.location', 'search_read',
                [[['id', 'in', location_ids]]],
                {'fields': ['id', 'name', 'usage', 'location_id']}
            )
            
            if not all_locations:
                return {
                    "qty_available": 0,
                    "virtual_available": 0,
                    "locations": [],
                    "product_name": product_name_with_attributes,
                    "sku": sku,
                    "found": True,
                    "uom": uom_name
                }
            
            # 7. Obtener información de bodegas
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
            
            # 8. Calcular stock disponible (como lo hace Odoo: quantity - reserved_quantity en ubicaciones internas)
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
            
            return {
                "qty_available": total_qty_available,
                "virtual_available": total_qty_virtual,
                "locations": locations_with_stock,
                "product_name": product_name_with_attributes,
                "sku": sku,
                "found": True,
                "uom": uom_name
            }
            
        except Exception as e:
            return {
                "qty_available": 0,
                "virtual_available": 0,
                "locations": [],
                "product_name": None,
                "sku": sku,
                "found": False,
                "error": str(e),
                "uom": None
            }

    def _get_stock_multiple_skus(self, skus):
        """
        Procesa múltiples SKUs en modo batch.
        """
        try:
            # 1. Buscar los IDs de los productos para todos los SKUs
            product_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'search',
                [[['default_code', 'in', skus]]]
            )
            
            if not product_ids:
                return {sku: {"found": False, "uom": None} for sku in skus}
            
            # 2. Leer la información de todos los productos encontrados
            products = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'read',
                [product_ids], {'fields': ['id', 'name', 'default_code', 'product_template_attribute_value_ids', 'uom_id']}
            )
            product_dict = {p['default_code']: p for p in products}
            
            # 3. Obtener información de UOM para todos los productos en una sola llamada
            uom_ids = list(set([p['uom_id'][0] for p in products if p['uom_id']]))
            uom_dict = {}
            if uom_ids:
                uom_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'uom.uom', 'read',
                    [uom_ids], {'fields': ['id', 'name']}
                )
                uom_dict = {uom['id']: uom['name'] for uom in uom_data}
            
            # 4. Buscar los stock quants para todos los productos encontrados
            stock_quants = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.quant', 'search_read',
                [[['product_id', 'in', product_ids]]],
                {'fields': ['product_id', 'quantity', 'location_id', 'reserved_quantity']}
            )
            
            # 5. Obtener información de ubicaciones que tienen quants
            location_ids = list(set([quant['location_id'][0] for quant in stock_quants]))
            
            if location_ids:
                all_locations = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'stock.location', 'search_read',
                    [[['id', 'in', location_ids]]],
                    {'fields': ['id', 'name', 'usage', 'location_id']}
                )
            else:
                all_locations = []
            
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
            
            # Crear diccionarios para mapear
            warehouse_dict = {warehouse['lot_stock_id'][0]: warehouse['name'] for warehouse in warehouses}
            location_dict = {loc['id']: loc for loc in all_locations}
            
            # 7. Agrupar quants por producto
            quants_by_product = {}
            for quant in stock_quants:
                pid = quant['product_id'][0]
                quants_by_product.setdefault(pid, []).append(quant)
            
            # 8. Procesar cada SKU
            results = {}
            for sku in skus:
                product = product_dict.get(sku)
                if not product:
                    results[sku] = {
                        "qty_available": 0,
                        "virtual_available": 0,
                        "locations": [],
                        "product_name": None,
                        "sku": sku,
                        "found": False,
                        "uom": None
                    }
                    continue
                
                # Obtener UOM del producto
                uom_name = None
                if product['uom_id']:
                    uom_name = uom_dict.get(product['uom_id'][0])
                
                # Obtener atributos de variante si existen
                attribute_values = []
                if product['product_template_attribute_value_ids']:
                    attribute_value_data = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'product.template.attribute.value', 'read',
                        [product['product_template_attribute_value_ids']], {'fields': ['name']}
                    )
                    attribute_values = [attr['name'] for attr in attribute_value_data]
                
                # Construir nombre completo del producto con atributos
                if attribute_values:
                    product_name_with_attributes = product['name'] + ' - ' + ', '.join(attribute_values)
                else:
                    product_name_with_attributes = product['name']
                
                # Obtener quants de este producto
                quants = quants_by_product.get(product['id'], [])
                
                if not quants:
                    results[sku] = {
                        "qty_available": 0,
                        "virtual_available": 0,
                        "locations": [],
                        "product_name": product_name_with_attributes,
                        "sku": sku,
                        "found": True,
                        "uom": uom_name
                    }
                    continue
                
                # Calcular stock disponible
                locations_with_stock = []
                total_qty_available = 0
                total_qty_virtual = 0
                
                for quant in quants:
                    location_id = quant['location_id'][0]
                    quantity = quant['quantity']
                    reserved_quantity = quant['reserved_quantity']
                    available_quantity = quantity - reserved_quantity
                    
                    location_data = location_dict.get(location_id)
                    if not location_data:
                        continue
                        
                    # Solo considerar ubicaciones internas para stock disponible
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
                    
                    # Para virtual, incluir todas las ubicaciones
                    total_qty_virtual += quantity
                
                results[sku] = {
                    "qty_available": total_qty_available,
                    "virtual_available": total_qty_virtual,
                    "locations": locations_with_stock,
                    "product_name": product_name_with_attributes,
                    "sku": sku,
                    "found": True,
                    "uom": uom_name
                }
            
            return results
            
        except Exception as e:
            return {"error": str(e)}

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
    
    def get_max_production_quantity(self, skus: List[str]):
        """Retorna la cantidad máxima de producción que se puede hacer de un producto, a partir del stock de los componentes"""
        from odoo_api import OdooProduct
        odoo_product = OdooProduct(
            db=self.db,
            url=self.url,
            username=self.username,
            password=self.password,
        )

        class BomItem:
            def __init__(self, sku: str, quantity: int, stock: int):
                self.sku = sku
                self.quantity = quantity
                self.stock = stock
                # Evitar división por cero y manejar cantidades inválidas
                if quantity <= 0:
                    self.max_quantity = 0.0
                else:
                    self.max_quantity = stock / quantity
            
            def __str__(self):
                return f"BomItem(sku={self.sku}, quantity={self.quantity}, stock={self.stock}, max_quantity={self.max_quantity})"

        product_bom_components = odoo_product.get_bom_components(skus)
        max_quantities = {}
        for sku, components in product_bom_components.items():
            bom_items = []
            
            # Verificar si hay componentes para este SKU
            if not components or len(components) == 0:
                # print(f"⚠️ Producto {sku} no tiene componentes de BOM o no se encontró BOM")
                max_quantities[sku] = 0.0
                continue
            
            for component in components:
                component_sku = component['sku']
                component_quantity = component['quantity']
                
                # Obtener stock del componente
                stock_info = self.get_stock_by_sku(component_sku)
                component_stock = stock_info.get('qty_available', 0) if stock_info else 0
                
                bom_items.append(BomItem(component_sku, component_quantity, component_stock))
            
            # Verificar si se crearon items de BOM válidos
            if not bom_items:
                # print(f"⚠️ No se pudieron crear items de BOM para el producto {sku}")
                max_quantities[sku] = 0.0
                continue
            
            # Calcular la cantidad máxima basada en el componente limitante
            max_quantity = min(bom_items, key=lambda x: x.max_quantity).max_quantity
            max_quantities[sku] = max_quantity

        return max_quantities

