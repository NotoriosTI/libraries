from .api import OdooAPI
import pandas as pd
from pprint import pprint

class OdooWarehouse(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    def get_stock_by_sku(self, sku):
        """
        Obtiene información de stock para un producto específico por SKU.
        
        Args:
            sku (str): SKU del producto a consultar
            
        Returns:
            dict: Información de stock consolidada
                {
                    "qty_available": float,
                    "virtual_available": float,
                    "locations": [
                        {"location": str, "quantity": float},
                        ...
                    ],
                    "product_name": str,
                    "sku": str
                }
        """
        # Obtener inventario completo
        df_inventory = self.read_stock_by_location()
        
        # Filtrar por SKU específico
        product_stock = df_inventory[df_inventory['internal_reference'] == sku]
        
        if product_stock.empty:
            return {
                "qty_available": 0,
                "virtual_available": 0,
                "locations": [],
                "product_name": None,
                "sku": sku,
                "found": False
            }
        
        # Consolidar información
        total_qty = product_stock['quantity'].sum()
        product_name = product_stock['product_id'].iloc[0] if not product_stock.empty else None
        
        # Crear lista de ubicaciones con stock
        locations = []
        for _, row in product_stock.iterrows():
            if row['quantity'] > 0:  # Solo mostrar ubicaciones con stock positivo
                locations.append({
                    "location": row['location'],
                    "warehouse": row['warehouse'],
                    "quantity": row['quantity']
                })
        
        return {
            "qty_available": total_qty,
            "virtual_available": total_qty,  # Por ahora igual que disponible
            "locations": locations,
            "product_name": product_name,
            "sku": sku,
            "found": True
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