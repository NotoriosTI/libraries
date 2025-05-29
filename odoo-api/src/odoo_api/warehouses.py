from .api import OdooAPI
import pandas as pd
from pprint import pprint

class OdooWarehouse(OdooAPI):
    def __init__(self):
        super().__init__()

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
    
    from .api import OdooAPI
import pandas as pd
from pprint import pprint

class OdooWarehouse(OdooAPI):
    def __init__(self, database='productive', dotenv_path=None): # Permitir pasar database y dotenv_path
        # Asegúrate de que el constructor de OdooAPI se llama correctamente.
        # Si OdooAPI no acepta dotenv_path directamente en __init__ y lo maneja de otra forma,
        # ajusta esta llamada. Basado en OdooProduct, OdooAPI debería aceptarlo.
        super().__init__(database=database, dotenv_path=dotenv_path)

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
            'product.product', 'read', [product_ids, ['default_code', 'name', 'product_template_attribute_value_ids', 'product_tag_ids']]) #

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
            if product_data['product_template_attribute_value_ids']: #
                attribute_value_data = self.models.execute_kw(self.db, self.uid, self.password,
                    'product.template.attribute.value', 'read', [product_data['product_template_attribute_value_ids'], ['name']]) #
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

    def get_variant_attributes_by_sku(self, sku: str) -> list:
        """
        Obtiene los nombres de los atributos de variante de un producto específico
        a partir de su SKU.

        Args:
            sku (str): El SKU (default_code) del producto.

        Returns:
            list: Una lista de nombres de atributos de la variante.
                  Devuelve una lista vacía si el producto no se encuentra,
                  no tiene atributos, o si ocurre un error.
        """
        if not sku:
            print("SKU no proporcionado.")
            return []

        try:
            # 1. Buscar el producto por SKU para obtener su ID y los IDs de sus atributos de variante.
            #    El campo 'default_code' usualmente almacena el SKU.
            #    El campo 'product_template_attribute_value_ids' contiene los IDs de los valores de atributos de la variante.
            product_info_list = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'search_read',
                [[['default_code', '=', sku]]],
                {'fields': ['id', 'name', 'product_template_attribute_value_ids'], 'limit': 1}
            )

            if not product_info_list:
                print(f"Producto con SKU '{sku}' no encontrado.")
                return []

            product_data = product_info_list[0]
            attribute_value_ids = product_data.get('product_template_attribute_value_ids')

            if not attribute_value_ids:
                # Esto puede significar que el producto no tiene variantes definidas por atributos
                # o que es un producto sin atributos específicos de variante.
                print(f"Producto con SKU '{sku}' (Nombre: {product_data.get('name')}) no tiene 'product_template_attribute_value_ids' o no es una variante con atributos.")
                return []

            # 2. Obtener los nombres de los atributos de la variante.
            #    Esta es la misma lógica que se usa en read_stock_by_location.
            attribute_names = []
            if attribute_value_ids:
                attribute_value_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'product.template.attribute.value', 'read',
                    [attribute_value_ids], {'fields': ['name']}
                ) #
                attribute_names = [attr['name'] for attr in attribute_value_data if 'name' in attr]
            
            return attribute_names

        except Exception as e:
            print(f"Error al obtener los atributos para el SKU '{sku}': {str(e)}")
            return []
