from .api import OdooAPI
import pandas as pd
import time
import xmlrpc.client
from pprint import pprint
import csv


class OdooProduct(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

# CRUD
    def create_product(self, product_data):
        # Verificar si el producto con el SKU dado ya existe
        if self.product_exists(product_data.get('default_code')):
            return f"El producto con código {product_data.get('default_code')} ya existe en Odoo."
        
        # Si no existe, crear el producto
        product_id = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'create', [product_data])
        
        if product_id:
            return f"Producto con código {product_data.get('default_code')} creado exitosamente en Odoo."
        else:
            return "Hubo un error al crear el producto en Odoo."

    def create_or_update_product(self, product_data):
        # Verificar si el producto con el SKU dado ya existe
        sku = str(product_data.get('default_code')).strip()
        barcode = product_data.get('barcode')

        product_by_sku = self.product_exists(sku)
        product_by_barcode = self.product_exists_by_barcode(barcode) if barcode else False

        # Check if 'categ_id' exists in product_data
        category_id = product_data.get('categ_id')

        if category_id is None:
            return f"La categoría no está especificada para el {sku}. Por favor, proporciona una categoría."

        
        # Decide el tipo de comando para campos Many2many basado en si el producto ya existe
        command_type = 'replace' if product_by_sku or product_by_barcode else 'add'
        
        # Procesa los campos Many2many
        if 'product_tag_ids' in product_data:
            product_data['product_tag_ids'] = self.process_field_value(product_data['product_tag_ids'], command_type)
        if 'route_ids' in product_data:
            product_data['route_ids'] = self.process_field_value(product_data['route_ids'], command_type)

        # Si un producto con el mismo SKU o código de barras ya existe, actualiza
        if product_by_sku or product_by_barcode:
            # Debugging: Verificar y imprimir detalles del producto con ese código de barras
            existing_product = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [[['barcode', '=', barcode]]], {'fields': ['default_code', 'name', 'barcode']})

            # Intentar actualizar
            try:
                response = self.update_product_from_data(sku, product_data)
                return f"Producto con código {sku} actualizado exitosamente: {response}"
            except Exception as e:
                return f"Error al actualizar el producto con código {sku}: {str(e)}"
        else:
            # Si no existe, intentar crear el producto
            try:
                product_id = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'create', [product_data])
                
                if product_id:
                    return f"Producto con código {sku} creado exitosamente en Odoo."
                else:
                    return "Hubo un error al crear el producto en Odoo."
            except Exception as e:
                return f"Error al crear el producto con código {sku}: {str(e)}"

    def read_product(self, sku):
        # Buscar el producto por el campo default_code
        product_ids = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search', [[['default_code', '=', sku]]])
        
        # Si el producto se encuentra, obtener sus detalles
        if product_ids:
            product_data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'read', [product_ids])
            return product_data
        else:
            return f"No se encontró el producto con código {sku}."

    def read_product_name(self, product_id):
        # Buscar el producto por su ID
        product_data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'read', [[product_id]])

        # Si el producto se encuentra, obtener su nombre
        if product_data:
            product_name = product_data[0].get('name', 'Nombre no disponible')
            return product_name
        else:
            return f"No se encontró el producto con ID {product_id}."
    
    def read_all_products_in_dataframe(self, batch_size=100):
        offset = 0
        all_products = []
        columns_to_drop = [
            "image_variant_1920", "image_variant_1024", "image_variant_512", "image_variant_256", 
            "image_variant_128", "can_image_variant_1024_be_zoomed", "image_1920", 
            "image_1024", "image_512", "image_256", "image_128", "can_image_1024_be_zoomed", 
            "website_product_name","website_description","website_short_description	website_seo_metatitle",
            "website_seo_description"
        ]
        
        while True:
            try:
                # Obtener IDs de productos en lotes con dominio vacío
                product_ids = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search', [[]], {'offset': offset, 'limit': batch_size})
                
                if not product_ids:
                    break
                
                # Obtener detalles de los productos
                products = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'read', [product_ids])
                all_products.extend(products)
                
                offset += batch_size
                
            except xmlrpc.client.ProtocolError as e:
                print(f"Error: {e}. Reintentando en 5 segundos...")
                time.sleep(5)
            except Exception as e:
                print(f"Error inesperado: {e}")
                break
        
        # Convertir a DataFrame
        df_products = pd.DataFrame(all_products)
        
        # Eliminar las columnas innecesarias si existen
        df_products = df_products.drop(columns=columns_to_drop, errors='ignore')

        return df_products if not df_products.empty else pd.DataFrame()

    def read_all_bills_of_materials_in_dataframe(self):
        """
        Read and return all Bills of Materials (BOMs) as a DataFrame.

        :return: A pandas DataFrame with columns: 
                 'manufactured_product_sku', 'component_product_sku', 'component_product_id', 'quantity_needed'
        """
        try:
            # Search for all BOMs
            bom_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'mrp.bom', 'search',
                [[]]
            )

            # Read BOM details
            boms = self.models.execute_kw(
                self.db, self.uid, self.password,
                'mrp.bom', 'read',
                [bom_ids],
                {'fields': ['id', 'product_tmpl_id', 'product_id','product_qty', 'bom_line_ids']}
            )

            bom_data = []

            for bom in boms:
                manufactured_product_id = bom['product_id'][0] if bom['product_id'] else None
                if manufactured_product_id:
                    quantity_to_manufactured = bom['product_qty']
                    
                    # Obtener las líneas de la BOM
                    bom_lines = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'mrp.bom.line', 'read',
                        [bom['bom_line_ids']],
                        {'fields': ['product_id', 'product_qty','product_uom_id']}
                    )

                    # Agregar los datos de las líneas de la BOM a bom_data
                    for line in bom_lines:
                        component_product_id = line['product_id'][0] if line['product_id'] else None
                        quantity_needed = line['product_qty']
                        uom = line['product_uom_id'][1] if line['product_uom_id'] else None

                        # Convertir de gramos a kilogramos si la unidad de medida es 'g'
                        if uom == 'g':
                            quantity_needed /= 1000
                            uom = 'kg'  # Actualizar la unidad de medida a 'kg'

                        bom_data.append({
                            'manufactured_product_id': manufactured_product_id,
                            'quantity_to_manufactured': quantity_to_manufactured,
                            'component_product_id': component_product_id,
                            'quantity_needed': quantity_needed,
                            'uom': uom
                        })
            # Create DataFrame
            df = pd.DataFrame(bom_data)

            # Convertir los IDs a cadenas (str)
            df['manufactured_product_id'] = df['manufactured_product_id'].astype(str)
            df['component_product_id'] = df['component_product_id'].astype(str)

            # Drop the original ID columns and reorder
            df = df[['manufactured_product_id', 'component_product_id', 'quantity_needed']]

            return df

        except Exception as e:
            print(f"Error al leer las listas de materiales: {str(e)}")
            return pd.DataFrame() 

    def read_all_product_tags(self):
        """
        Retrieve all existing tags that belong to products.

        :return: A pandas DataFrame containing the id and name of all product tags
        """
        model = 'product.tag'
        domain = []  # Empty domain to get all records
        fields = ['id', 'name']

        tags = self.models.execute_kw(self.db, self.uid, self.password, 
                                    model, 'search_read', [domain], {'fields': fields})

        # Convert the list of dictionaries to a pandas DataFrame
        df_tags = pd.DataFrame(tags)

        return df_tags

    def update_product_from_data(self, sku, product_data):
        # Buscar el producto por el campo default_code
        product_ids = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search', [[['default_code', '=', sku]]])
        
        # Si el producto se encuentra, actualizar los campos
        if product_ids:
            product_id = product_ids[0]
            self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'write', [product_id, product_data])
            return "Actualizado con éxito"
        else:
            return f"No se encontró el producto con código {sku}."

    def update_inventory_by_sku(self, sku, new_quantity, location_id):
       
        # Buscar el producto por el campo default_code
        product_ids = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search', [[['default_code', '=', sku]]])
        if product_ids:
            # Si el producto se encuentra, actualizar los campos
            print('El producto ha sido ubicado exitosamente')
            product_id = product_ids[0]

            # Buscar el quant para el producto y la ubicación
            quant_ids = self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'search', [[['product_id', '=', product_id], ['location_id', '=', location_id]]])
            # Si existe un quant, actualizamos la cantidad
            if quant_ids:
                quant_id = quant_ids[0]
                self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'write', [[quant_id], {'quantity': new_quantity}])
                
            # Si no existe un quant, creamos uno nuevo
            else:
                self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'create', [{
                    'product_id': product_id,
                    'location_id': location_id,
                    'quantity': new_quantity,
                }])
            
            return "Inventario actualizado con éxito"
        else:
            return f"No se encontró el producto con código {sku}."

# Other Functions
    def product_exists(self, sku) -> bool:
        """
        Verifica si el producto ya existe en Odoo basándose en el SKU y que el producto esté habilitado para la venta (sale_ok=True).
        """
        product_ids = self.models.execute_kw(
            self.db, self.uid, self.password,
            'product.product', 'search',
            [[
                ['default_code', '=', str(sku).strip()],
                ['sale_ok', '=', True]
            ]]
        )
        return bool(product_ids)

    def process_field_value(self, value, command_type='add'):
        # Convertir la entrada a una lista de IDs
        if isinstance(value, str):
            if "," in value:
                ids = [int(id_.strip()) for id_ in value.split(",")]
            elif "-" in value:
                start, end = [int(id_.strip()) for id_ in value.split("-")]
                ids = list(range(start, end + 1))
            else:
                ids = [int(value.strip())]
        elif isinstance(value, int):
            ids = [value]
        else:
            raise ValueError(f"Tipo de entrada no válido: {type(value)}")

        # Convertir la lista de IDs a los comandos de Odoo
        if command_type == 'add':
            return [(4, id_) for id_ in ids]
        elif command_type == 'replace':
            return [(6, 0, ids)]
        elif command_type == 'remove':
            return [(5,)]
        else:
            raise ValueError(f"Invalid command_type: {command_type}")

    def get_category_id_by_name(self, category_name):
        # Check if category_name is None or an empty string
        if not category_name:
            return None

        # Perform the search in the 'product.category' model
        category_ids = self.models.execute_kw(self.db, self.uid, self.password, 'product.category', 'search', [[['name', '=', category_name]]])
        if category_ids:
            return category_ids[0]
        else:
            return None

    def update_product_quantities(self,product_data): #Recibe csv con product_data
        error_data = []

        # Split the product data by comma to get the individual fields
        warehouse_id, product_id, name, stock, fecha, hora, sku = product_data
        try:
            id_product_odoo = self.get_id_by_sku(sku)
            # Search for the product template ID using the product ID
            product_template_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'read',
                [id_product_odoo], {'fields': ['product_tmpl_id']}
            )[0]['product_tmpl_id'][0]
            # Create a new stock.change.product.qty record
            if float(stock)>=0:
                stock_change_product_qty_id = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'stock.change.product.qty', 'create',
                    [{
                        'product_id': id_product_odoo,
                        'product_tmpl_id': product_template_id,
                        'new_quantity': stock,
                    }]
                )
            elif float(stock)<0:
                stock_change_product_qty_id = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'stock.change.product.qty', 'create',
                    [{
                        'product_id': id_product_odoo,
                        'product_tmpl_id': product_template_id,
                        'new_quantity': 0,
                    }]
                )

            # Trigger the change_product_qty method to update the product quantity
            self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.change.product.qty', 'change_product_qty',
                [stock_change_product_qty_id]
            )
            updated_product_data = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'product.product', 'read',
                    [id_product_odoo], {'fields': ['qty_available']}
                )[0]
            updated_stock = updated_product_data['qty_available']
            if float(updated_stock) != float(stock):
                print(f'Failed to update stock for product {id_product_odoo} (SKU: {sku}). Expected {stock}, got {updated_stock}.')
            else:
                print(f'Successfully updated stock for product {id_product_odoo} (SKU: {sku}) to {updated_stock}.')        
        except Exception as e:
            print(f'Error processing product {product_id} (SKU: {sku}): {e}')
            return sku

    def read_model_fields(self,model_name):
        try:
            fields = self.models.execute_kw(self.db, self.uid, self.password,model_name, 'fields_get', [])
            df_fields = pd.DataFrame.from_dict(fields, orient='index')
            return df_fields
        except Exception as e:
            print(f"Error retrieving fields for model: {e}")
            return None

    def read_work_centers(self):
        """
        Obtiene una lista de centros de trabajo de Odoo.
        """
        try:
            work_centers = self.models.execute_kw(
                self.db, self.uid, self.password,
                'mrp.routing.workcenter', 'search_read',
                [[]], {'fields': ['id', 'name']}
            )
            return work_centers
        except Exception as e:
            print("Error al obtener los centros de trabajo: ", e)
            return []

    def inventory_adjustment_by_warehouse(self, warehouse_name):
        warehouses_info = {
            'Bodega de Materias Primas': {
                'csv_path': '/home/sam/Spacionatural/Data/Recent_Data/Stock/Stock_by_warehouse/warehouse_2_stock.csv',
                'location_id': 24 
            },
            'Bodega de Envases': {
                'csv_path': '/home/sam/Spacionatural/Data/Recent_Data/Stock/Stock_by_warehouse/warehouse_3_stock.csv',
                'location_id': 23
            },
            'Tienda Juan Sabaj': {
                'csv_path': '/home/sam/Spacionatural/Data/Recent_Data/Stock/Stock_by_warehouse/warehouse_4_stock.csv',
                'location_id' : 8
            },
            'Mercado Libre':{
                'csv_path': '/home/sam/Spacionatural/Data/Recent_Data/Stock/Stock_by_warehouse/warehouse_8_stock.csv',
                'location_id' : 25
            },
            'Picking': {
                'csv_path': '/home/sam/Spacionatural/Data/Recent_Data/Stock/Stock_by_warehouse/warehouse_9_stock.csv',
                'location_id' : 26
            }
        }

        try:
            warehouse_info = warehouses_info[warehouse_name]
        except KeyError:
            raise ValueError(f"Nombre de almacén '{warehouse_name}' no reconocido o escrito incorrectamente.")

        csv_file_path = warehouse_info['csv_path']
        location_id = warehouse_info['location_id']

        inventory_adjustment_val = {
            'name': 'Ajuste Inventario ODOO API',
            'location_ids':[(4,location_id)]
        }
        inventory_adjustment_id = self.models.execute_kw(
            self.db, self.uid, self.password, 
            'stock.inventory', 'create', [inventory_adjustment_val]
        )

        try:
            with open(csv_file_path, mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    product_id = self.get_id_by_sku(str(row['productId'])) 
                    product_qty = float(row['stock']) 
                    if product_qty<0:
                        product_qty==0 
                    line_vals = {
                        'inventory_id': inventory_adjustment_id,
                        'product_id': product_id,
                        'location_id': location_id,
                        'product_qty': product_qty
                    }

                    self.models.execute_kw(
                        self.db, self.uid, self.password, 
                        'stock.inventory.line', 'create', [line_vals]
                    )
                self.models.execute_kw(
                        self.db, self.uid, self.password, 
                        'stock.inventory', 'action_validate', [[inventory_adjustment_id]]
                    )

        except Exception as e:
            raise Exception(f"Error al procesar el archivo CSV o al validar el ajuste de inventario: {e}")

# Este método debe reemplazar al existente en tu clase OdooProduct dentro de product.py

    def create_production_orders(self, df_production):
        """
        Crea órdenes de producción en Odoo basándose en el DataFrame dado.
        El SKU en el DataFrame debe corresponder al product.product (variante o producto sin variantes).
        Busca BOMs de forma flexible: primero por variante específica, luego por plantilla genérica.
        """
        output = ''
        for index, row in df_production.iterrows():
            sku = str(row['SKU']).strip() # SKU del product.product
            quantity = row['TOTAL PRODUCCIÓN']
            picking_quantity = row['A PRODUCIR PICKING (1 MES)']

            # 1. Obtener detalles del producto (product.product) y su plantilla asociada
            #    El método read_product busca en product.product por default_code (SKU)
            product_details_list = self.read_product(sku)

            if isinstance(product_details_list, str) or not product_details_list:
                output += f"SKU {sku}: Producto (variante) no encontrado o error al leer detalles ({product_details_list}). Se omite orden.\n"
                continue
            
            product_data = product_details_list[0] # Tomamos el primer resultado

            if 'id' not in product_data or 'product_tmpl_id' not in product_data:
                output += f"SKU {sku}: No se pudieron obtener ID de producto o ID de plantilla. Detalles: {product_data}. Se omite orden.\n"
                continue

            product_variant_id = product_data['id'] # ID del product.product (variante)
            product_template_info = product_data.get('product_tmpl_id') # Es una tupla [id, nombre_display]
            product_template_id = product_template_info[0] if product_template_info else None

            # 2. Lógica mejorada para buscar la BOM activa
            bom_id_to_use = None
            bom_search_result_ids = []

            # 2a. Intentar buscar BOM activa por product.product (variante específica)
            if product_variant_id:
                # print(f"DEBUG: Buscando BOM para SKU {sku} por product_id (variante): {product_variant_id}") # Para depuración
                bom_search_result_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'mrp.bom', 'search',
                    [[('product_id', '=', product_variant_id), ('active', '=', True)]],
                    {'limit': 1} 
                )
            
            if bom_search_result_ids:
                bom_id_to_use = bom_search_result_ids[0]
                # print(f"DEBUG: BOM encontrada por variante para SKU {sku}. BOM ID: {bom_id_to_use}") # Para depuración
            else:
                # 2b. Si no se encontró por variante, intentar por product.template (plantilla)
                #     Asegurándose de que sea una BOM genérica de plantilla (product_id = False) y activa.
                if product_template_id:
                    # print(f"DEBUG: Buscando BOM para SKU {sku} por product_tmpl_id (plantilla): {product_template_id}") # Para depuración
                    bom_search_result_ids = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'mrp.bom', 'search',
                        [[('product_tmpl_id', '=', product_template_id),
                          ('product_id', '=', False), 
                          ('active', '=', True)]],
                        {'limit': 1}
                    )
                
                if bom_search_result_ids:
                    bom_id_to_use = bom_search_result_ids[0]
                    # print(f"DEBUG: BOM encontrada por plantilla para SKU {sku}. BOM ID: {bom_id_to_use}") # Para depuración

            if not bom_id_to_use:
                output += f"SKU {sku}: No se encontró una Lista de Materiales activa (ni por variante específica ni por plantilla genérica). Se omite creación de orden.\n"
                continue
            
            # 4. Crear la orden de producción para la variante específica
            production_order_vals = {
                'product_id': product_variant_id, # MUY IMPORTANTE: la orden es para el product.product (variante)
                'product_qty': quantity,
                'bom_id': bom_id_to_use,
                'location_dest_id': 8, # Ubicación destino hardcodeada (Stock Total Juan Sabaj)
                # Considerar añadir 'company_id' si es un entorno multi-compañía
            }

            try:
                production_order_id = self.models.execute_kw(self.db, self.uid, self.password, 'mrp.production', 'create', [production_order_vals])
                output += f"SKU {sku}: Orden de producción creada con ID: {production_order_id} para la variante ID: {product_variant_id}.\n"

                # 5. Crear transferencia interna de picking (lógica existente)
                source_location_id = 8
                destination_location_id = 29
                picking_type_id_internal = 5 # ID para 'transferencia-interna'
                
                picking_vals = {
                    'location_id': source_location_id,
                    'location_dest_id': destination_location_id,
                    'picking_type_id': picking_type_id_internal,
                }
                picking_id = self.models.execute_kw(self.db, self.uid, self.password, 'stock.picking', 'create', [picking_vals])

                move_vals = {
                    'product_id': product_variant_id, # El movimiento es para la variante
                    'product_uom_qty': picking_quantity,
                    'name': f'Picking para OP del SKU {sku}',
                    'picking_id': picking_id,
                    'location_id': source_location_id,
                    'location_dest_id': destination_location_id,
                }
                self.models.execute_kw(self.db, self.uid, self.password, 'stock.move', 'create', [move_vals])
                output += f"SKU {sku}: Transferencia interna (ID: {picking_id}) para picking creada.\n"

            except Exception as e_create:
                output += f"SKU {sku}: Error al crear orden de producción o picking: {str(e_create)}\n"
            
        return output
    
    def search_production_orders(self, sku):
            # Use the read_product function to get the product ID
            product_data = self.read_product(sku)
            if not isinstance(product_data, list):
                return product_data  # Return the error message if product is not found

            product_id = product_data[0]['id']  # Assuming the first product ID is the one we need

            # Search for production orders with the product
            production_order_count = self.models.execute_kw(self.db, self.uid, self.password, 'mrp.production', 'search_count', [[['product_id', '=', product_id]]])

            return production_order_count > 0

    def get_field_selection_options(self, model, field_name):
        """
        Get selection options for a specific field in a model.
        
        :param model: The model name (e.g., 'product.template')
        :param field_name: The field name to get selection options for
        :return: A list of tuples with the field's selection options and descriptions
        """
        # Fetching the details of the field
        field_details = self.models.execute_kw(
            self.db, self.uid, self.password, 
            model, 'fields_get', 
            [], {'attributes': ['type', 'selection']}
        )

        # Check if the field exists and is of type 'selection'
        if field_name in field_details and field_details[field_name]['type'] == 'selection':
            return field_details[field_name]['selection']
        else:
            return None

    def search_read(self, model, fields):
        """
        Search for records based on the model and fields and read their data.

        :param model: The model name (e.g., 'res.bank')
        :param fields: List of fields to be read
        :return: A list of dictionaries containing the data of each record
        """
        return self.models.execute_kw(self.db, self.uid, self.password, 
                                      model, 'search_read', [[]], {'fields': fields})

    def get_id_by_sku(self, sku):
        """
        Retrieve the product ID based on the SKU.

        :param sku: The SKU of the product
        :return: The ID of the product or None if not found
        """
        model = 'product.product'  # or 'product.template' based on your Odoo setup
        domain = [('default_code', '=', sku)]  # 'default_code' is typically used for SKU
        fields = ['id']

        product = self.models.execute_kw(self.db, self.uid, self.password, model, 'search_read', [domain], {'fields': fields})

        if product:
            return product[0]['id']  # Return the ID of the first product found
        else:
            return None
        
    def get_sku_by_id(self, product_id):
        """
        Get the product SKU by ID
        :param product_id: The ID of the product
        :return: The SKU (default_code) of the product or None if not found
        """
        if product_id is None:
            return None

        try:
            # Convert product_id to integer
            product_id = int(float(product_id))
        except ValueError:
            print(f"Invalid product ID: {product_id}")
            return None

        model = 'product.product'  # or 'product.template' based on your Odoo setup
        domain = [('id', '=', product_id)]
        fields = ['default_code']

        product = self.models.execute_kw(self.db, self.uid, self.password, model, 'search_read', [domain], {'fields': fields})

        if product:
            return product[0]['default_code']  # Return the SKU of the first product found
        else:
            return None
    
    def get_skus_by_name_flexible(self, partial_name) -> list[dict]:
        """
        Devuelve una lista de diccionarios {id:str, default_code(sku): str, name:str} de productos cuyo nombre contenga el texto dado (insensible a mayúsculas/minúsculas).
        :param partial_name: Texto parcial del nombre del producto
        :return: Lista de diccionarios {"id", "default_code": str, "name": str}
        """
        model = 'product.product'
        domain = [('name', 'ilike', partial_name)]
        fields = ['id', 'default_code', 'name']

        db_check, uid_check, pass_check = self.db, self.uid, self.password
        products = self.models.execute_kw(self.db, self.uid, self.password, model, 'search_read', [domain], {'fields': fields})
        return products
        
    
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
            print(f"Error while getting attributes for SKU '{sku}': {str(e)}")
            return []
    
    def get_last_mo_draft(self) -> dict:
        """Returns dict of the id, product_name and product_qty of the latest mo draft on Odoo"""
        try:
            result = self.models.execute_kw(
                self.db, self.uid, self.password,
                'mrp.production', 'search_read',
                [[['state', '=', 'draft']]], {
                    'fields': ['id', 'name', 'product_id', 'product_qty'],
                    'limit': 1,
                    'order': 'id desc'
                }
            )
        except Exception as e:
            print(f"Error while getting the last MO from Odoo:\n{e}")
        
        mo = result[0]

        if not mo:
            print("Error while obtaining MO. returning empty dict")
            return {}

        mo_id = mo.get('id', None)
        mo_name = mo.get('name', None)
        _, product_name = mo.get('product_id', [None, None])
        product_qty = mo.get('product_qty', None)


        if not (mo_id and product_qty and product_name and mo_name):
            print("Error while obtaining MO data. Returning empty dict")
            return {}
        
        return {
            "mo_id": mo_id,
            "mo_name": mo_name,
            "product_name": product_name,
            "product_qty": product_qty
        }
    
    def confirm_mo(self, mo_id: int):
        """
        Confirms a draft Manufacturing order(MO) using it's id
        :param mo_id: ID of the MO to confirm
        :return: True if correctly confirmed False if error occurs
        """
        try:
            result = self.models.execute_kw(
                self.db, self.uid, self.password,
                'mrp.production', 'action_confirm',
                [[mo_id]]
            )
        except Exception as e:
            print(f"Error while confirming MO {mo_id}: {e}")
            return False
        print(f"MO {mo_id} confirmed!")
        return True
    