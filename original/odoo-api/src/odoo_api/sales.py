from datetime import datetime, timedelta
from .api import OdooAPI
import pandas as pd

class OdooSales(OdooAPI):
    """
    Clase para manejar operaciones relacionadas con ventas en Odoo
    """
    def __init__(self, database='productive'):
        super().__init__(database=database)
    
    def read_sales_by_day(self, day):
        """
        Lee todas las ventas de un día específico
        
        :param day: datetime.date objeto con la fecha a consultar
        :return: DataFrame con las ventas del día o mensaje de error
        """
        try:
            # Convertir el día a datetime si es necesario
            if isinstance(day, str):
                day = datetime.strptime(day, '%Y-%m-%d').date()
            
            # Crear rango de fechas para el día
            start_date = datetime.combine(day, datetime.min.time())
            end_date = datetime.combine(day, datetime.max.time())
            
            # Dominio para la búsqueda
            domain = [
                ('state', 'in', ['sale', 'done']),  # Solo ventas confirmadas
                ('date_order', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_order', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            # Campos a obtener
            fields = [
                'name',           # Número de orden
                'date_order',     # Fecha de la orden
                'partner_id',     # Cliente
                'amount_total',   # Monto total
                'state',          # Estado
                'order_line'      # Líneas de la orden
            ]
            
            # Buscar las ventas
            sales = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [domain],
                {'fields': fields}
            )
            
            # Convertir a DataFrame
            df = pd.DataFrame(sales)
            
            # Si hay datos, procesar las líneas de orden
            if not df.empty and 'order_line' in df.columns:
                # Lista para almacenar los detalles de las líneas
                all_lines = []
                
                for _, row in df.iterrows():
                    if row['order_line']:
                        line_details = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'sale.order.line', 'read',
                            [row['order_line']],
                            {'fields': ['product_id', 'product_uom_qty', 'price_unit', 'price_subtotal']}
                        )
                        all_lines.extend(line_details)
                
                # Convertir detalles de líneas a DataFrame
                df_lines = pd.DataFrame(all_lines)
                
                # Aquí podrías hacer un merge si necesitas relacionar las líneas con las órdenes
            
            return df
            
        except Exception as e:
            return f"Error al leer las ventas del día {day}: {str(e)}"
    
    def read_all_sales(self, limit=None, offset=0):
        """
        Lee todas las ventas registradas en el sistema
        
        :param limit: Número máximo de registros a retornar (opcional)
        :param offset: Número de registros a saltar (para paginación)
        :return: DataFrame con las ventas o mensaje de error
        """
        try:
            # Quitar el límite de prueba
            sales_domain = [
                ('state', 'in', ['sale', 'done'])
            ]
            
            sales_fields = [
                'name',
                'date_order',
                'partner_id',
                'amount_total',
                'state',
                'user_id',
                'team_id',
                'order_line',
            ]
            
            sales = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [sales_domain],
                {'fields': sales_fields}
            )
            
            # 2. Obtener ventas POS
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ]
            
            pos_fields = [
                'name',
                'date_order',
                'partner_id',
                'amount_total',
                'state',
                'user_id',
                'lines',
            ]
            
            pos_orders = self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read',
                [pos_domain],
                {'fields': pos_fields}
            )
            
            # Convertir ambos a DataFrames
            df_sales = pd.DataFrame(sales)
            df_pos = pd.DataFrame(pos_orders)
            
            # Combinar los DataFrames
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            
            # Obtener todos los partner_ids únicos
            partner_ids = []
            for sale in sales + pos_orders:
                if sale.get('partner_id'):
                    partner_ids.append(sale['partner_id'][0])
            partner_ids = list(set(partner_ids))  # Eliminar duplicados
            
            # Obtener información de los partners
            if partner_ids:
                partners = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'res.partner', 'read',
                    [partner_ids],
                    {'fields': ['id', 'vat', 'l10n_latam_identification_type_id']}
                )
                partners_dict = {p['id']: p for p in partners}
            else:
                partners_dict = {}
            
            # Procesar líneas de productos
            all_lines = []
            
            # Procesar líneas de ventas regulares
            for _, row in df_sales.iterrows():
                if row['order_line']:
                    line_details = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'sale.order.line', 'read',
                        [row['order_line']],
                        {'fields': [
                            'order_id',
                            'product_id',
                            'product_uom_qty',
                            'price_unit',
                            'price_subtotal',
                            'name'
                        ]}
                    )
                    
                    for line in line_details:
                        if line['product_id']:
                            product_info = self.models.execute_kw(
                                self.db, self.uid, self.password,
                                'product.product', 'read',
                                [line['product_id'][0]],
                                {'fields': ['default_code', 'name']}
                            )[0]
                            
                            line_data = {
                                'sale_order': row['name'],
                                'items_product_sku': product_info.get('default_code', ''),
                                'items_product_description': product_info.get('name', ''),
                                'items_quantity': line['product_uom_qty'],
                                'items_unitPrice': line['price_unit'],
                                'price_subtotal': line['price_subtotal']
                            }
                            all_lines.append(line_data)
            
            # Procesar líneas de POS
            for _, row in df_pos.iterrows():
                if row['lines']:
                    line_details = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'pos.order.line', 'read',
                        [row['lines']],
                        {'fields': [
                            'product_id',
                            'qty',
                            'price_unit',
                            'price_subtotal',
                            'name'
                        ]}
                    )
                    
                    for line in line_details:
                        if line['product_id']:
                            product_info = self.models.execute_kw(
                                self.db, self.uid, self.password,
                                'product.product', 'read',
                                [line['product_id'][0]],
                                {'fields': ['default_code', 'name']}
                            )[0]
                            
                            line_data = {
                                'sale_order': row['name'],
                                'items_product_sku': product_info.get('default_code', ''),
                                'items_product_description': product_info.get('name', ''),
                                'items_quantity': line['qty'],
                                'items_unitPrice': line['price_unit'],
                                'price_subtotal': line['price_subtotal']
                            }
                            all_lines.append(line_data)
            
            # Combinar los DataFrames de ventas y POS
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            df_lines = pd.DataFrame(all_lines)
            
            # Procesar campos comunes
            if 'amount_total' in df.columns:
                df['totals_net'] = (df['amount_total'] / 1.19).round(0)
                df['totals_vat'] = (df['amount_total'] - df['totals_net']).round(0)
                df['total_total'] = df['amount_total']
            
            if 'user_id' in df.columns:
                df['salesman_name'] = df['user_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
            
            # Determinar el canal de venta
            df['sales_channel'] = df.apply(
                lambda x: "Tienda Sabaj" if (
                    isinstance(x.get('name'), str) and 'Juan Sabaj' in x['name']  # Solo si el docnumber contiene "Juan Sabaj"
                ) else (
                    x['team_id'][1] if isinstance(x.get('team_id'), (list, tuple)) else None
                ),
                axis=1
            )
            
            if 'partner_id' in df.columns:
                df['customer_name'] = df['partner_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
                df['customer_customerid'] = df['partner_id'].apply(lambda x: x[0] if isinstance(x, (list, tuple)) else None)
                df['customer_vatid'] = df.apply(
                    lambda x: partners_dict.get(x['partner_id'][0], {}).get('vat', '') if isinstance(x['partner_id'], (list, tuple)) else '',
                    axis=1
                )
            
            # Añadir campos vacíos
            df['term_name'] = None
            df['warehouse_name'] = None
            df['doctype_name'] = None
            
            # Asignar fecha de emisión
            df['issuedDate'] = df['date_order']
            
            # Asignar salesInvoiceId y docnumber
            df['salesInvoiceId'] = df['id']
            df['docnumber'] = df['name']
            
            # Limpiar columnas innecesarias
            df = df.drop(['order_line', 'user_id', 'team_id', 'partner_id', 'date_order', 'name', 'id'], axis=1, errors='ignore')
            
            return {'orders': df, 'lines': df_lines}
            
        except Exception as e:
            return f"Error al leer todas las ventas: {str(e)}"
    
    def read_sales_by_date_range(self, start_date, end_date):
        """
        Lee las ventas dentro de un rango de fechas con los mismos datos que read_all_sales
        
        :param start_date: datetime.date inicio del rango
        :param end_date: datetime.date fin del rango
        :return: DataFrame con las ventas o mensaje de error
        """
        try:
            # Convertir fechas si son strings
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Crear rango de fechas
            start = datetime.combine(start_date, datetime.min.time())
            end = datetime.combine(end_date, datetime.max.time())
            
            # 1. Obtener ventas regulares
            sales_domain = [
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', start.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_order', '<=', end.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            sales_fields = [
                'name',
                'date_order',
                'partner_id',
                'amount_total',
                'state',
                'user_id',
                'team_id',
                'order_line',
            ]
            
            sales = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [sales_domain],
                {'fields': sales_fields}
            )
            
            # 2. Obtener ventas POS
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced']),
                ('date_order', '>=', start.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_order', '<=', end.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            pos_fields = [
                'name',
                'date_order',
                'partner_id',
                'amount_total',
                'state',
                'user_id',
                'lines',
            ]
            
            pos_orders = self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read',
                [pos_domain],
                {'fields': pos_fields}
            )
            
            # Convertir ambos a DataFrames
            df_sales = pd.DataFrame(sales)
            df_pos = pd.DataFrame(pos_orders)
            
            # Obtener todos los partner_ids únicos
            partner_ids = []
            for sale in sales + pos_orders:
                if sale.get('partner_id'):
                    partner_ids.append(sale['partner_id'][0])
            partner_ids = list(set(partner_ids))
            
            # Obtener información de los partners
            if partner_ids:
                partners = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'res.partner', 'read',
                    [partner_ids],
                    {'fields': ['id', 'vat', 'l10n_latam_identification_type_id']}
                )
                partners_dict = {p['id']: p for p in partners}
            else:
                partners_dict = {}
            
            # Procesar líneas de productos
            all_lines = []
            
            # Procesar líneas de ventas regulares
            if not df_sales.empty:
                for _, row in df_sales.iterrows():
                    if row['order_line']:
                        line_details = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'sale.order.line', 'read',
                            [row['order_line']],
                            {'fields': [
                                'order_id',
                                'product_id',
                                'product_uom_qty',
                                'price_unit',
                                'price_subtotal',
                                'name'
                            ]}
                        )
                        
                        for line in line_details:
                            if line['product_id']:
                                product_info = self.models.execute_kw(
                                    self.db, self.uid, self.password,
                                    'product.product', 'read',
                                    [line['product_id'][0]],
                                    {'fields': ['default_code', 'name']}
                                )[0]
                                
                                line_data = {
                                    'sale_order': row['name'],
                                    'items_product_sku': product_info.get('default_code', ''),
                                    'items_product_description': product_info.get('name', ''),
                                    'items_quantity': line['product_uom_qty'],
                                    'items_unitPrice': line['price_unit'],
                                    'price_subtotal': line['price_subtotal']
                                }
                                all_lines.append(line_data)
            
            # Procesar líneas de POS
            if not df_pos.empty:
                for _, row in df_pos.iterrows():
                    if row['lines']:
                        line_details = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'pos.order.line', 'read',
                            [row['lines']],
                            {'fields': [
                                'product_id',
                                'qty',
                                'price_unit',
                                'price_subtotal',
                                'name'
                            ]}
                        )
                        
                        for line in line_details:
                            if line['product_id']:
                                product_info = self.models.execute_kw(
                                    self.db, self.uid, self.password,
                                    'product.product', 'read',
                                    [line['product_id'][0]],
                                    {'fields': ['default_code', 'name']}
                                )[0]
                                
                                line_data = {
                                    'sale_order': row['name'],
                                    'items_product_sku': product_info.get('default_code', ''),
                                    'items_product_description': product_info.get('name', ''),
                                    'items_quantity': line['qty'],
                                    'items_unitPrice': line['price_unit'],
                                    'price_subtotal': line['price_subtotal']
                                }
                                all_lines.append(line_data)
            
            # Combinar los DataFrames de ventas y POS
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            df_lines = pd.DataFrame(all_lines)
            
            if not df.empty:
                # Procesar campos comunes
                if 'amount_total' in df.columns:
                    df['totals_net'] = (df['amount_total'] / 1.19).round(0)
                    df['totals_vat'] = (df['amount_total'] - df['totals_net']).round(0)
                    df['total_total'] = df['amount_total']
                
                if 'user_id' in df.columns:
                    df['salesman_name'] = df['user_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
                
                # Determinar el canal de venta
                df['sales_channel'] = df.apply(
                    lambda x: "Tienda Sabaj" if (
                        isinstance(x.get('name'), str) and 'Juan Sabaj' in x['name']  # Solo si el docnumber contiene "Juan Sabaj"
                    ) else (
                        x['team_id'][1] if isinstance(x.get('team_id'), (list, tuple)) else None
                    ),
                    axis=1
                )
                
                if 'partner_id' in df.columns:
                    df['customer_name'] = df['partner_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
                    df['customer_customerid'] = df['partner_id'].apply(lambda x: x[0] if isinstance(x, (list, tuple)) else None)
                    df['customer_vatid'] = df.apply(
                        lambda x: partners_dict.get(x['partner_id'][0], {}).get('vat', '') if isinstance(x['partner_id'], (list, tuple)) else '',
                        axis=1
                    )
                
                # Añadir campos vacíos
                df['term_name'] = None
                df['warehouse_name'] = None
                df['doctype_name'] = None
                
                # Asignar fecha de emisión
                df['issuedDate'] = df['date_order']
                
                # Asignar salesInvoiceId y docnumber
                df['salesInvoiceId'] = df['id']
                df['docnumber'] = df['name']
                
                # Limpiar columnas innecesarias
                df = df.drop(['order_line', 'user_id', 'team_id', 'partner_id', 'date_order', 'name', 'id'], axis=1, errors='ignore')
                
                return {'orders': df, 'lines': df_lines}
            
            return {'orders': df, 'lines': df_lines}
            
        except Exception as e:
            return f"Error al leer las ventas entre {start_date} y {end_date}: {str(e)}"
