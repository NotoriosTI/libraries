from .api import OdooAPI
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('odoo_crm')

class OdooCRM(OdooAPI):

    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)
    
    def create_oportunity(self, data, tag=None):
        """
        Crea una nueva oportunidad en el CRM
        
        :param data: Diccionario con los datos de la oportunidad
        :param tag: Nombre de la etiqueta a asignar (ej: 'Creado por Emma')
        """
        try:
            print(f"\nIntentando crear oportunidad con datos: {data}")
            
            # Si se proporciona una etiqueta, buscar su ID
            tag_ids = []
            if tag:
                # Buscar el ID de la etiqueta por nombre
                found_tags = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'crm.tag', 'search_read',
                    [[['name', '=', tag]]],
                    {'fields': ['id']}
                )
                
                if found_tags:
                    tag_ids = [found_tags[0]['id']]
                else:
                    print(f"Advertencia: No se encontró la etiqueta '{tag}'")
            
            # Añadir tags específicos a la lista de tags existente
            if data.get('tag_ids'):
                tag_ids.extend(data.get('tag_ids'))
            
            # Campos mínimos requeridos para crear una oportunidad
            required_fields = {
                'name': data.get('name'),
                'partner_id': data.get('partner_id'),
                'expected_revenue': data.get('expected_revenue', 0.0),
                'probability': data.get('probability', 0.0),
                'type': 'opportunity',
            }
            
            # Campos opcionales comunes
            optional_fields = {
                'team_id': data.get('team_id'),
                'user_id': data.get('user_id'),
                'description': data.get('description'),
                'date_deadline': data.get('date_deadline'),
                'priority': data.get('priority', '1'),
                'tag_ids': [(6, 0, tag_ids)] if tag_ids else None,
            }
            
            # Combinar campos y filtrar los valores None
            opportunity_data = {**required_fields, **optional_fields}
            opportunity_data = {k: v for k, v in opportunity_data.items() if v is not None}
            
            print(f"\nDatos finales para crear oportunidad: {opportunity_data}")
            
            # Crear la oportunidad
            opportunity_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'create',
                [opportunity_data]
            )
            
            print(f"\nID de oportunidad creada: {opportunity_id}")
            
            # Verificar inmediatamente después de crear
            created_opp = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'read',
                [opportunity_id],
                {'fields': ['name', 'type', 'partner_id']}
            )
            print(f"\nVerificación inmediata de la oportunidad creada: {created_opp}")
            
            return opportunity_id
            
        except Exception as e:
            print(f"\nError detallado al crear oportunidad: {str(e)}")
            return f"Error al crear la oportunidad: {str(e)}"

    def create_quotation_from_opportunity(self, opportunity_id, order_lines):
        """
        Crea una cotización desde una oportunidad usando el método nativo de Odoo
        
        :param opportunity_id: ID de la oportunidad
        :param order_lines: Lista de diccionarios con los productos
            [
                {
                    'product_id': 123,      # ID del producto
                    'product_uom_qty': 1.0,  # Cantidad
                },
                ...
            ]
        :return: ID de la cotización creada o mensaje de error
        """
        try:
            # 1. Obtener información de la oportunidad
            opportunity = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'read',
                [opportunity_id],
                {'fields': ['partner_id', 'team_id', 'user_id']}
            )[0]
            
            # 2. Crear la cotización directamente
            quotation_data = {
                'partner_id': opportunity['partner_id'][0],
                'opportunity_id': opportunity_id,
                'team_id': opportunity.get('team_id', False) and opportunity['team_id'][0],
                'user_id': opportunity.get('user_id', False) and opportunity['user_id'][0],
                'state': 'draft',
            }
            
            sale_order_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'create',
                [quotation_data]
            )

            sale_order_info = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'read',
                [sale_order_id],
                {'fields': ['name']}
            )

            sale_order_name = sale_order_info[0]['name']
            
            
            # 3. Agregar las líneas de producto
            for line in order_lines:
                # Obtener información completa del producto y sus variantes
                product_info = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'product.product', 'read',
                    [line['product_id']],
                    {'fields': ['uom_id', 'name', 'list_price', 'price_extra']}
                )[0]
                
                # Calcular el precio final considerando el precio extra de la variante
                final_price = product_info['list_price'] + (product_info.get('price_extra', 0.0) or 0.0)
                
                line_data = {
                    'order_id': sale_order_id,
                    'product_id': line['product_id'],
                    'product_uom_qty': line.get('product_uom_qty', 1.0),
                    'product_uom': product_info['uom_id'][0],
                    'name': product_info['name'],
                    'price_unit': line.get('price_unit', final_price),  # Usamos el precio final calculado
                }
                
                line_id = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'sale.order.line', 'create',
                    [line_data]
                )
                
                if not line_id:
                    return f"Error: No se pudo crear la línea para el producto {product_info['name']}"
            
            return sale_order_name, sale_order_id
            
        except Exception as e:
            return f"Error al crear la cotización: {str(e)}"
    
    def read_oportunity_by_id(self, id):
        """
        Lee una oportunidad específica por su ID
        
        :param id: ID de la oportunidad
        :return: DataFrame con los datos de la oportunidad o mensaje de error
        """
        try:
            fields = [
                'name',
                'partner_id',
                'expected_revenue',
                'probability',
                'team_id',
                'user_id',
                'description',
                'date_deadline',
                'priority',
                'tag_ids',
                'stage_id',
                'create_date',
                'write_date',
                'email_from',
                'phone',
            ]
            
            opportunity = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'read',
                [id],
                {'fields': fields}
            )
            
            if opportunity:
                df = pd.DataFrame([opportunity[0]])
                return df
            else:
                return "Oportunidad no encontrada"
            
        except Exception as e:
            return f"Error al leer la oportunidad: {str(e)}"

    def read_stages(self, domain=None, return_as_dict=False):
        """
        Lee todas las etapas disponibles en el CRM
        
        :param domain: Lista de condiciones para filtrar las etapas (opcional)
        :param return_as_dict: Si es True, retorna un diccionario {nombre: id}
        :return: DataFrame con las etapas o diccionario nombre->id o mensaje de error
        """
        try:
            # Campos a recuperar (eliminado 'probability' que no existe en este modelo)
            fields = [
                'id',
                'name',
                'sequence',
                'fold',
                'is_won',
                'requirements'
            ]
            
            # Si no se especifica un dominio, usar lista vacía
            domain = domain or []
            
            # Buscar todas las etapas
            stage_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.stage', 'search',
                [domain]
            )
            
            if not stage_ids:
                return "No se encontraron etapas"
            
            # Leer datos de las etapas
            stages = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.stage', 'read',
                [stage_ids],
                {'fields': fields}
            )
            
            if return_as_dict:
                # Retornar como diccionario nombre -> id para fácil acceso
                return {stage['name']: stage['id'] for stage in stages}
            
            # Convertir a DataFrame
            df = pd.DataFrame(stages)
            return df
            
        except Exception as e:
            return f"Error al leer las etapas: {str(e)}"
    
    def read_all_opportunities_in_df(self, domain=None, limit=None):
        """
        Lee todas las oportunidades que coincidan con el dominio especificado
        
        :param domain: Lista de condiciones para filtrar las oportunidades (opcional)
        :param limit: Número máximo de registros a retornar (opcional)
        :return: DataFrame con las oportunidades o mensaje de error
        """
        try:
            # Campos a recuperar
            fields = [
                'name',
                'partner_id',
                'expected_revenue',
                'probability',
                'team_id',
                'user_id',
                'description',
                'date_deadline',
                'priority',
                'tag_ids',
                'stage_id',
                'create_date',
                'write_date',
                'email_from',
                'phone',
                'order_ids',
            ]
            
            # Si no se especifica un dominio, usar lista vacía
            domain = domain or []
            
            # Buscar IDs de oportunidades
            opportunity_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'search',
                [domain],
                {'limit': limit} if limit else {}
            )
            
            if not opportunity_ids:
                return "No se encontraron oportunidades"
            
            # Leer datos de las oportunidades
            opportunities = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'read',
                [opportunity_ids],
                {'fields': fields}
            )
            
            # Convertir a DataFrame
            df = pd.DataFrame(opportunities)
            return df
            
        except Exception as e:
            return f"Error al leer las oportunidades: {str(e)}"

    def read_order_info(self, order_id):
        """
        Obtiene información detallada de una orden/cotización específica
        
        Args:
            order_id (int): ID de la orden en Odoo
            
        Returns:
            dict: Información de la orden (name, amount_total, etc.) o mensaje de error
        """
        try:
            fields = [
                'name',            # Número/código de la orden (S00XX)
                'amount_total',    # Monto total
                'state',           # Estado
                'date_order',      # Fecha
                'partner_id',      # Cliente
                'opportunity_id',  # Oportunidad relacionada
            ]
            
            order_info = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'read',
                [[order_id]],
                {'fields': fields}
            )
            
            if order_info and len(order_info) > 0:
                return order_info[0]
            else:
                return f"No se encontró la orden con ID {order_id}"
            
        except Exception as e:
            return f"Error al obtener información de la orden: {str(e)}"

    def update_order_payment_status(self, order_id, payment_data):
        """
        Actualiza el estado de pago de una orden
        
        Args:
            order_id (int): ID de la orden en Odoo
            payment_data (dict): Datos del pago (payment_id, date, etc.)
            
        Returns:
            bool: True si la actualización fue exitosa o mensaje de error
        """
        try:
            # Verificar que la orden existe
            order_exists = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search',
                [[['id', '=', order_id]]]
            )
            
            if not order_exists:
                return f"No se encontró la orden con ID {order_id}"
            
            # Actualizar el estado de pago de la orden
            update_data = {
                'x_payment_reference': payment_data.get('payment_id', ''),
                'x_payment_date': payment_data.get('date', datetime.now().strftime('%Y-%m-%d')),
                'x_is_paid': True
            }
            
            self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'write',
                [[order_id], update_data]
            )
            
            return True
            
        except Exception as e:
            return f"Error al actualizar el estado de pago de la orden: {str(e)}"

    def update_order_status(self, order_id, status='confirm'):
        """
        Actualiza el estado de una orden
        
        Args:
            order_id (int): ID de la orden en Odoo
            status (str): Estado a aplicar ('confirm', 'cancel', etc.)
            
        Returns:
            bool: True si la actualización fue exitosa o mensaje de error
        """
        try:
            # Verificar que la orden existe
            order_exists = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search',
                [[['id', '=', order_id]]]
            )
            
            if not order_exists:
                return f"No se encontró la orden con ID {order_id}"
            
            # Aplicar la acción según el estado solicitado
            if status == 'confirm':
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'sale.order', 'action_confirm',
                    [[order_id]]
                )
            elif status == 'cancel':
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'sale.order', 'action_cancel',
                    [[order_id]]
                )
            # Se pueden agregar más estados según sea necesario
            
            return True
            
        except Exception as e:
            return f"Error al actualizar el estado de la orden: {str(e)}"

    def update_oportunity_by_id(self, id, data):
        """
        Actualiza una oportunidad existente por su ID
        
        :param id: ID de la oportunidad a actualizar
        :param data: diccionario con los campos a actualizar
        :return: True si la actualización fue exitosa o mensaje de error
        """
        try:
            # Verificar que la oportunidad existe
            existing = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'search_count', # Usar search_count es más eficiente
                [[('id', '=', id)]]
            )
            
            if existing == 0:
                logger.error(f"Intento de actualizar oportunidad ID {id} fallido: No encontrada.")
                return "Oportunidad no encontrada"

            # Actualizar la oportunidad
            result = self.models.execute_kw(
                self.db, self.uid, self.password,
                'crm.lead', 'write',
                [[id], data]
            )

            if result: # write devuelve True en éxito
                 logger.info(f"Oportunidad ID {id} actualizada exitosamente con datos: {data}")
                 return True
            else:
                 # Esto es inusual si la ID existe y los datos son válidos
                 logger.warning(f"La actualización de la oportunidad ID {id} devolvió False.")
                 return "La actualización no reportó éxito (posiblemente sin cambios)."

        except Exception as e:
            logger.error(f"Error al actualizar la oportunidad ID {id}: {str(e)}")
            # Considera devolver la excepción o un mensaje más específico si es posible
            return f"Error al actualizar la oportunidad: {str(e)}"

    def read_or_create_tag(self, tag_name: str) -> int:
        """
        Busca una etiqueta (crm.tag) por nombre. Si no existe, la crea.
        Devuelve el ID de la etiqueta.
        """
        model_name = 'crm.tag'
        domain = [('name', '=', tag_name)]
        fields = ['id']
        existing_tags = self.models.execute_kw(
            self.db, self.uid, self.password,
            model_name, 'search_read',
            [domain], {'fields': fields, 'limit': 1}
        )

        if existing_tags:
            tag_id = existing_tags[0]['id']
            logger.info(f"Etiqueta encontrada: '{tag_name}' (ID: {tag_id})")
            return tag_id
        else:
            try:
                new_tag_id = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    model_name, 'create',
                    [{'name': tag_name}]
                )
                if isinstance(new_tag_id, int):
                    logger.info(f"Etiqueta creada: '{tag_name}' (ID: {new_tag_id})")
                    return new_tag_id
                else:
                    # Si create no devuelve un ID, buscarlo (puede depender de la versión/configuración de Odoo)
                    created_tag = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        model_name, 'search_read',
                        [domain], {'fields': fields, 'limit': 1}
                    )
                    if created_tag:
                        logger.info(f"Etiqueta creada y encontrada: '{tag_name}' (ID: {created_tag[0]['id']})")
                        return created_tag[0]['id']
                    else:
                        logger.error(f"Se intentó crear la etiqueta '{tag_name}', pero no se pudo encontrar después.")
                        raise Exception(f"Error al verificar la creación de la etiqueta '{tag_name}'")

            except Exception as e:
                logger.error(f"Error al crear la etiqueta '{tag_name}': {e}")
                raise

    def read_active_opportunities_by_customer(self, customer_id: int, fields_to_read: list = None) -> pd.DataFrame:
        """
        Busca oportunidades activas (no ganadas/cerradas) para un cliente específico.
        """
        lead_model = 'crm.lead'
        stage_model = 'crm.stage'

        # Buscar IDs de etapas que se consideran "cerradas" (ganadas o perdidas)
        closed_stage_domain = [('is_won', '=', True)]
        try:
            closed_stages = self.models.execute_kw(
                self.db, self.uid, self.password,
                stage_model, 'search_read',
                [closed_stage_domain], {'fields': ['id']}
            )
            closed_stage_ids = [stage['id'] for stage in closed_stages]
            logger.info(f"IDs de etapas cerradas/ganadas encontradas: {closed_stage_ids}")

            # Dominio para buscar oportunidades activas del cliente
            opportunity_domain = [
                ('partner_id', '=', customer_id),
                ('stage_id', 'not in', closed_stage_ids),
                ('type', '=', 'opportunity') # Asegurar que sean oportunidades
            ]

            # Campos por defecto a leer si no se especifican
            if fields_to_read is None:
                fields_to_read = [
                    'id', 'name', 'expected_revenue', 'stage_id',
                    'tag_ids', 'order_ids', 'partner_id' # Incluir partner_id para consistencia
                ]

            opportunities = self.models.execute_kw(
                self.db, self.uid, self.password,
                lead_model, 'search_read',
                [opportunity_domain], {'fields': fields_to_read}
            )
            logger.info(f"Encontradas {len(opportunities)} oportunidades activas para el cliente ID {customer_id}.")
            if not opportunities:
                return pd.DataFrame(columns=fields_to_read) # Devolver DataFrame vacío si no hay resultados

            df = pd.DataFrame(opportunities)
            # Las listas de IDs ya vienen en el formato correcto desde search_read
            return df

        except Exception as e:
            logger.error(f"Error al leer oportunidades activas para el cliente ID {customer_id}: {e}")
            return pd.DataFrame(columns=fields_to_read)

    def read_opportunity_type(self, opportunity_data: dict) -> str:
        """
        Determina el tipo de oportunidad (Odoo/Shopify) basado en etiquetas o fallback.
        """
        tag_model = 'crm.tag'
        sale_order_model = 'sale.order'
        tag_ids = opportunity_data.get('tag_ids', [])
        order_ids = opportunity_data.get('order_ids', [])
        opportunity_id_log = opportunity_data.get('id', 'N/A') # Para logs

        if not tag_ids:
            logger.warning(f"Oportunidad ID {opportunity_id_log} no tiene etiquetas. Intentando fallback.")
        else:
            try:
                # Leer los nombres de las etiquetas asociadas
                tags = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    tag_model, 'read',
                    [tag_ids], {'fields': ['name']}
                )
                tag_names = [tag['name'].lower() for tag in tags]

                if 'emma-odoo' in tag_names:
                    logger.info(f"Oportunidad ID {opportunity_id_log} identificada como 'Odoo' por etiqueta.")
                    return "Odoo"
                if 'emma-shopify' in tag_names:
                    logger.info(f"Oportunidad ID {opportunity_id_log} identificada como 'Shopify' por etiqueta.")
                    return "Shopify"
                logger.warning(f"Oportunidad ID {opportunity_id_log} tiene etiquetas, pero ninguna es 'emma-odoo' o 'emma-shopify'. Etiquetas: {tag_names}. Intentando fallback.")

            except Exception as e:
                logger.error(f"Error al leer nombres de etiquetas para oportunidad ID {opportunity_id_log}: {e}. Intentando fallback.")

        # --- Fallback Logic ---
        if order_ids:
            try:
                first_order_id = order_ids[0]
                order_info_list = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    sale_order_model, 'read',
                    [first_order_id], {'fields': ['name']}
                )
                if order_info_list:
                    order_name = order_info_list[0].get('name', '')
                    if order_name.startswith('S0'):
                        logger.info(f"Oportunidad ID {opportunity_id_log} identificada como 'Odoo' por fallback (nombre orden: {order_name}).")
                        return "Odoo"
                    if order_name.startswith('SN-'):
                        logger.info(f"Oportunidad ID {opportunity_id_log} identificada como 'Shopify' por fallback (nombre orden: {order_name}).")
                        return "Shopify"
                    else:
                        logger.warning(f"Oportunidad ID {opportunity_id_log} tiene orden ({order_name}) pero el nombre no coincide con los prefijos de fallback ('S0', 'SN-').")
                else:
                    logger.warning(f"No se pudo leer la información de la orden ID {first_order_id} para el fallback.")
            except Exception as e:
                logger.error(f"Error durante el fallback al leer la orden ID {first_order_id} para la oportunidad ID {opportunity_id_log}: {e}")
        else:
            logger.info(f"Oportunidad ID {opportunity_id_log} no tiene etiquetas relevantes ni órdenes asociadas para el fallback.")

        logger.warning(f"No se pudo determinar el tipo para la oportunidad ID {opportunity_id_log}.")
        return "Unknown"

    def read_sale_order(self, order_id: int, fields: list = None) -> dict:
        """Lee una orden de venta por su ID."""
        model_name = 'sale.order'
        if fields is None:
            fields = ['id', 'name', 'state', 'order_line', 'partner_id', 'opportunity_id']
        try:
            orders = self.models.execute_kw(
                self.db, self.uid, self.password,
                model_name, 'read',
                [order_id], {'fields': fields} # read espera una lista de IDs, aunque sea uno
            )
            if orders:
                logger.info(f"Orden de venta ID {order_id} leída exitosamente.")
                return orders[0]
            else:
                logger.warning(f"No se encontró la orden de venta con ID {order_id}.")
                return None
        except Exception as e:
            logger.error(f"Error al leer la orden de venta ID {order_id}: {e}")
            return None

    def update_sale_order_lines(self, order_id: int, product_lines_data: list):
        """
        Reemplaza las líneas de una orden de venta existente.
        Asegura que product_lines_data tenga el formato correcto para crear sale.order.line.
        """
        order_model = 'sale.order'
        product_model = 'product.product'
        # line_model = 'sale.order.line' # No es necesario para obtener info de producto si usamos execute_kw

        lines_to_create = []
        for line_data in product_lines_data:
            if 'product_id' not in line_data or 'product_uom_qty' not in line_data:
                logger.error(f"Datos de línea inválidos para orden {order_id}: falta product_id o product_uom_qty. Datos: {line_data}")
                continue

            if 'name' not in line_data or 'price_unit' not in line_data or 'product_uom' not in line_data:
                try:
                    product_info_list = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        product_model, 'read',
                        [line_data['product_id']], {'fields': ['name', 'list_price', 'uom_id', 'price_extra']}
                    )
                    if not product_info_list:
                         logger.error(f"No se encontró información para el producto ID {line_data['product_id']}.")
                         continue # Saltar esta línea si no se encuentra el producto
                    product_info = product_info_list[0]

                    if 'name' not in line_data:
                        line_data['name'] = product_info['name']
                    if 'price_unit' not in line_data:
                        final_price = product_info['list_price'] + (product_info.get('price_extra', 0.0) or 0.0)
                        line_data['price_unit'] = final_price
                    if 'product_uom' not in line_data and product_info.get('uom_id'):
                        line_data['product_uom'] = product_info['uom_id'][0]
                    elif 'product_uom' not in line_data:
                        logger.error(f"Falta 'product_uom' y no se pudo obtener del producto ID {line_data['product_id']}. Saltando línea.")
                        continue # Saltar si no se puede determinar la unidad de medida

                except Exception as e:
                    logger.error(f"Error obteniendo detalles del producto ID {line_data['product_id']} para la orden {order_id}: {e}. Saltando línea.")
                    continue

            lines_to_create.append((0, 0, line_data))

        if not lines_to_create and product_lines_data:
            logger.error(f"No se pudieron preparar líneas válidas para actualizar la orden {order_id}.")
            return False

        try:
            update_payload = {
                'order_line': [(5, 0, 0)] + lines_to_create
            }
            result = self.models.execute_kw(
                self.db, self.uid, self.password,
                order_model, 'write',
                [[order_id], update_payload]
            )
            if result:
                logger.info(f"Líneas de la orden de venta ID {order_id} actualizadas exitosamente.")
                return True
            else:
                logger.warning(f"La actualización de líneas para la orden {order_id} no devolvió éxito.")
                return False
        except Exception as e:
            logger.error(f"Error al actualizar las líneas de la orden de venta ID {order_id}: {e}")
            return False

    def get_closed_stage_ids(self) -> list:
        """Obtiene una lista de IDs de las etapas consideradas cerradas (ganadas/perdidas)."""
        stage_model = 'crm.stage'
        closed_stage_domain = [('is_won', '=', True)]
        try:
            closed_stages = self.models.execute_kw(
                self.db, self.uid, self.password,
                stage_model, 'search_read',
                [closed_stage_domain], {'fields': ['id']}
            )
            closed_stage_ids = [stage['id'] for stage in closed_stages]
            logger.info(f"IDs de etapas cerradas/ganadas recuperadas: {closed_stage_ids}")
            return closed_stage_ids
        except Exception as e:
            logger.error(f"Error al obtener IDs de etapas cerradas: {e}")
            return [] # Devolver lista vacía en caso de error
