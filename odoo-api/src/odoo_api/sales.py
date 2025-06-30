from datetime import datetime, timedelta
from .api import OdooAPI
import pandas as pd
import pytz

class OdooSales(OdooAPI):
    """
    Clase para manejar operaciones relacionadas con ventas en Odoo
    """
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)
        self._user_timezone = None
    
    def get_user_timezone(self):
        """
        Obtiene la zona horaria del usuario actual (por defecto Santiago)
        """
        if self._user_timezone is None:
            try:
                user_info = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'res.users', 'read',
                    [self.uid],
                    {'fields': ['tz']}
                )[0]
                self._user_timezone = user_info.get('tz', 'America/Santiago')
            except:
                self._user_timezone = 'America/Santiago'
        return self._user_timezone
    
    def _convert_timezone(self, day, user_timezone):
        """
        Convierte un día en zona horaria local a rango UTC para consultas API
        
        :param day: datetime.date - fecha a convertir
        :param user_timezone: str - zona horaria del usuario (ej: 'America/Santiago')
        :return: tuple (start_date_utc, end_date_utc) como strings
        """
        # Crear objetos de zona horaria
        local_tz = pytz.timezone(user_timezone)
        utc_tz = pytz.UTC
        
        # Crear fechas en hora local
        local_start = local_tz.localize(datetime.combine(day, datetime.min.time()))
        local_end = local_tz.localize(datetime.combine(day, datetime.max.time()))
        
        # Convertir a UTC para la API de Odoo
        utc_start = local_start.astimezone(utc_tz)
        utc_end = local_end.astimezone(utc_tz)
        
        start_date = utc_start.strftime('%Y-%m-%d %H:%M:%S')
        end_date = utc_end.strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"🌍 Zona horaria: {user_timezone}")
        print(f"📅 Hora local: {local_start.strftime('%Y-%m-%d %H:%M:%S')} a {local_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 UTC para API: {start_date} a {end_date}")
        
        return start_date, end_date
    
    def _convert_timezone_range(self, start_date, end_date, user_timezone):
        """
        Convierte un rango de fechas en zona horaria local a rango UTC para consultas API
        
        :param start_date: datetime.date - fecha de inicio
        :param end_date: datetime.date - fecha de fin
        :param user_timezone: str - zona horaria del usuario
        :return: tuple (start_date_utc, end_date_utc) como strings
        """
        # Crear objetos de zona horaria
        local_tz = pytz.timezone(user_timezone)
        utc_tz = pytz.UTC
        
        # Crear fechas en hora local (inicio del primer día, fin del último día)
        local_start = local_tz.localize(datetime.combine(start_date, datetime.min.time()))
        local_end = local_tz.localize(datetime.combine(end_date, datetime.max.time()))
        
        # Convertir a UTC para la API de Odoo
        utc_start = local_start.astimezone(utc_tz)
        utc_end = local_end.astimezone(utc_tz)
        
        start_date_utc = utc_start.strftime('%Y-%m-%d %H:%M:%S')
        end_date_utc = utc_end.strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"🌍 Zona horaria: {user_timezone}")
        print(f"📅 Rango local: {local_start.strftime('%Y-%m-%d %H:%M:%S')} a {local_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Rango UTC para API: {start_date_utc} a {end_date_utc}")
        
        return start_date_utc, end_date_utc
    
    def _get_sales_orders(self, start_utc, end_utc):
        """
        Obtiene órdenes de venta regulares con filtros estándar
        
        :param start_utc: fecha inicio en UTC
        :param end_utc: fecha fin en UTC
        :return: lista de órdenes de venta
        """
        sales_domain = [
            ('state', 'in', ['sale', 'done']),
            ('invoice_status', '=', 'invoiced'),  # Solo órdenes completamente facturadas
            # ('invoice_status', 'in', ['invoiced', 'to invoice']),  # Incluir también "Para facturar"
            ('date_order', '>=', start_utc),
            ('date_order', '<=', end_utc)
        ]
        
        sales_fields = [
            'name', 'date_order', 'partner_id', 'amount_total', 
            'state', 'user_id', 'team_id', 'order_line'
        ]
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'search_read',
            [sales_domain],
            {'fields': sales_fields}
        )
    
    def _get_pos_orders(self, start_utc, end_utc):
        """
        Obtiene órdenes POS (si hay permisos)
        
        :param start_utc: fecha inicio en UTC
        :param end_utc: fecha fin en UTC
        :return: lista de órdenes POS
        """
        try:
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced']),
                ('date_order', '>=', start_utc),
                ('date_order', '<=', end_utc)
            ]
            
            pos_fields = [
                'name', 'date_order', 'partner_id', 'amount_total',
                'state', 'user_id', 'lines'
            ]
            
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read',
                [pos_domain],
                {'fields': pos_fields}
            )
        except Exception as e:
            print(f"⚠️  Sin permisos para POS, continuando solo con ventas regulares: {str(e)[:100]}...")
            return []
    
    def _get_partners_info(self, orders_list):
        """
        Obtiene información de partners para las órdenes
        
        :param orders_list: lista combinada de órdenes (sales + pos)
        :return: diccionario con información de partners
        """
        partner_ids = []
        for order in orders_list:
            if order.get('partner_id'):
                partner_ids.append(order['partner_id'][0])
        partner_ids = list(set(partner_ids))
        
        if partner_ids:
            partners = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'read',
                [partner_ids],
                {'fields': ['id', 'vat', 'l10n_latam_identification_type_id']}
            )
            return {p['id']: p for p in partners}
        return {}
    
    def _process_sale_lines(self, df_sales):
        """
        Procesa líneas de productos de órdenes de venta regulares
        
        :param df_sales: DataFrame con órdenes de venta
        :return: lista de líneas procesadas
        """
        all_lines = []
        if df_sales.empty:
            return all_lines
            
        for _, row in df_sales.iterrows():
            if row['order_line']:
                line_details = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'sale.order.line', 'read',
                    [row['order_line']],
                    {'fields': [
                        'order_id', 'product_id', 'product_uom_qty',
                        'price_unit', 'price_subtotal', 'name'
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
        return all_lines
    
    def _process_pos_lines(self, df_pos):
        """
        Procesa líneas de productos de órdenes POS
        
        :param df_pos: DataFrame con órdenes POS
        :return: lista de líneas procesadas
        """
        all_lines = []
        if df_pos.empty:
            return all_lines
            
        for _, row in df_pos.iterrows():
            if row['lines']:
                try:
                    line_details = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'pos.order.line', 'read',
                        [row['lines']],
                        {'fields': [
                            'product_id', 'qty', 'price_unit',
                            'price_subtotal', 'name'
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
                except Exception as e:
                    print(f"⚠️  Error procesando líneas POS: {str(e)[:50]}...")
        return all_lines
    
    def _transform_orders_data(self, df, partners_dict):
        """
        Aplica transformaciones comunes a los datos de órdenes
        
        :param df: DataFrame con órdenes combinadas
        :param partners_dict: diccionario con información de partners
        :return: DataFrame transformado
        """
        if df.empty:
            return df
            
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
                isinstance(x.get('name'), str) and 'Juan Sabaj' in x['name']
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
        
        # Mapear términos de pago y almacén
        if 'payment_term_id' in df.columns:
            df['term_name'] = df['payment_term_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else None)
        else:
            df['term_name'] = None
            
        if 'warehouse_id' in df.columns:
            df['warehouse_name'] = df['warehouse_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else None)
        else:
            df['warehouse_name'] = None
            
        # Asignar tipo de documento
        df['doctype_name'] = 'Factura'
        
        # Asignar fecha de emisión
        df['issuedDate'] = df['date_order']
        
        # Asignar salesInvoiceId y docnumber
        df['salesInvoiceId'] = df['id']
        df['docnumber'] = df['name']
        
        # Limpiar columnas innecesarias
        df = df.drop(['order_line', 'user_id', 'team_id', 'partner_id', 'date_order', 'name', 'id', 'payment_term_id', 'warehouse_id'], axis=1, errors='ignore')
        
        return df
    
    def read_sales_by_day(self, day):
        """
        Lee todas las ventas de un día específico usando la zona horaria del usuario
        
        :param day: datetime.date objeto con la fecha a consultar
        :return: DataFrame con las ventas del día o mensaje de error
        """
        try:
            # Convertir el día a datetime si es necesario
            if isinstance(day, str):
                day = datetime.strptime(day, '%Y-%m-%d').date()
            
            # Obtener la zona horaria del usuario y convertir fechas
            user_tz_name = self.get_user_timezone()
            start_date, end_date = self._convert_timezone(day, user_tz_name)
            
            # Obtener órdenes de venta usando el método helper
            sales_orders = self._get_sales_orders(start_date, end_date)
            
            # Convertir a DataFrame
            df = pd.DataFrame(sales_orders)
            
            print(f"🎯 Órdenes encontradas con conversión UTC: {len(df)}")
            
            # Si hay datos, procesar las líneas de orden usando método helper
            if not df.empty and 'order_line' in df.columns:
                all_lines = self._process_sale_lines(df)
                df_lines = pd.DataFrame(all_lines)
                # Aquí podrías hacer un merge si necesitas relacionar las líneas con las órdenes
            
            return df
            
        except Exception as e:
            return f"Error al leer las ventas del día {day}: {str(e)}"
    

    def _get_all_sales_orders_optimized(self, limit=1000, offset=0, days_back=None):
        """
        Obtiene órdenes de venta con optimizaciones de rendimiento
        
        :param limit: Número máximo de registros (default: 1000)
        :param offset: Registros a saltar para paginación
        :param days_back: Días hacia atrás desde hoy (None = sin filtro de fecha)
        :return: lista de órdenes de venta optimizada
        """
        from datetime import datetime, timedelta
        
        # Dominio base con filtros estándar
        sales_domain = [
            ('state', 'in', ['sale', 'done']),
            ('invoice_status', '=', 'invoiced'),  # Solo órdenes completamente facturadas
        ]
        
        # Agregar filtro por fecha solo si se especifica days_back
        if days_back is not None:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            sales_domain.append(('date_order', '>=', cutoff_date))
        
        # Campos mínimos necesarios
        sales_fields = [
            'name', 'date_order', 'partner_id', 'amount_total',
            'state', 'user_id', 'team_id', 'order_line',
            'payment_term_id', 'warehouse_id'  # Agregados para term_name y warehouse_name
        ]
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'search_read',
            [sales_domain],
            {
                'fields': sales_fields,
                'limit': limit,
                'offset': offset,
                'order': 'date_order DESC'  # Más recientes primero
            }
        )
    
    def _get_all_pos_orders_optimized(self, limit=1000, offset=0, days_back=None):
        """
        Obtiene órdenes POS con optimizaciones de rendimiento
        
        :param limit: Número máximo de registros
        :param offset: Registros a saltar para paginación  
        :param days_back: Días hacia atrás desde hoy (None = sin filtro de fecha)
        :return: lista de órdenes POS optimizada
        """
        try:
            from datetime import datetime, timedelta
            
            # Dominio base para POS
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced']),
            ]
            
            # Agregar filtro por fecha solo si se especifica days_back
            if days_back is not None:
                cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
                pos_domain.append(('date_order', '>=', cutoff_date))
            
            pos_fields = [
                'name', 'date_order', 'partner_id', 'amount_total',
                'state', 'user_id', 'lines'
            ]
            
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read',
                [pos_domain],
                {
                    'fields': pos_fields,
                    'limit': limit,
                    'offset': offset,
                    'order': 'date_order DESC'
                }
            )
        except Exception as e:
            print(f"⚠️  Sin permisos para POS, continuando solo con ventas regulares: {str(e)[:100]}...")
            return []


    def read_sales_by_date_range(self, start_date, end_date, limit=None, include_lines=True, batch_size=500):
        """
        Lee las ventas dentro de un rango de fechas usando conversión de zona horaria (OPTIMIZADO)
        
        Esta función ofrece múltiples optimizaciones para diferentes casos de uso:
        - Procesamiento batch para grandes volúmenes de datos
        - Control de inclusión de líneas de productos
        - Límites de registros para pruebas y dashboards
        - Batch size personalizable para gestión de memoria
        
        :param start_date: datetime.date inicio del rango
        :param end_date: datetime.date fin del rango
        :param limit: límite de órdenes a procesar (None = sin límite)
        :param include_lines: si incluir líneas de productos (False para solo órdenes)
        :param batch_size: tamaño del lote para procesamiento de líneas
        :return: Dict con 'orders' (DataFrame) y 'lines' (DataFrame) o mensaje de error
        
        Casos de uso recomendados:
        
        # 📊 DASHBOARDS Y REPORTES RÁPIDOS (solo totales)
        result = sales.read_sales_by_date_range(
            start_date, end_date, 
            include_lines=False  # 3-5x más rápido
        )
        
        # 📈 ANÁLISIS DETALLADO COMPLETO (con líneas de productos)
        result = sales.read_sales_by_date_range(
            start_date, end_date, 
            include_lines=True  # Datos completos
        )
        
        # 🔬 PRUEBAS Y DESARROLLO (datasets limitados)
        result = sales.read_sales_by_date_range(
            start_date, end_date, 
            limit=100,  # Solo 100 órdenes
            include_lines=True
        )
        
        # 💾 SISTEMAS CON MEMORIA LIMITADA (batch pequeño)
        result = sales.read_sales_by_date_range(
            start_date, end_date,
            batch_size=100  # Lotes más pequeños
        )
        
        # ⚡ MÁXIMO RENDIMIENTO (memoria abundante)
        result = sales.read_sales_by_date_range(
            start_date, end_date,
            batch_size=1000  # Lotes más grandes
        )
        
        # 🚀 RESÚMENES EJECUTIVOS (súper rápido)
        result = sales.read_sales_by_date_range(
            start_date, end_date,
            limit=50,
            include_lines=False  # Solo órdenes principales
        )
        
        Rendimiento esperado:
        - Sin líneas (include_lines=False): 3-5x más rápido
        - Con límite: Reduce tiempo proporcionalmente
        - Batch grande (500-1000): Menos consultas, más rápido
        - Batch pequeño (50-200): Más consultas, menos memoria
        """
        try:
            # Convertir fechas si son strings
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            print(f"🚀 OPTIMIZADO: Buscando ventas entre {start_date} y {end_date}")
            print(f"📊 Límite: {limit or 'Sin límite'}, Líneas: {'SÍ' if include_lines else 'NO'}")
            
            # Obtener la zona horaria del usuario y convertir fechas
            user_tz_name = self.get_user_timezone()
            start_utc, end_utc = self._convert_timezone_range(start_date, end_date, user_tz_name)
            
            # 1. Obtener ventas regulares optimizadas
            sales_orders = self._get_sales_orders_optimized(start_utc, end_utc, limit)
            
            # 2. Obtener ventas POS optimizadas (si hay permisos)
            pos_orders = self._get_pos_orders_optimized(start_utc, end_utc, limit)
            
            print(f"📊 Órdenes obtenidas: {len(sales_orders)} ventas + {len(pos_orders)} POS")
            
            # Convertir ambos a DataFrames
            df_sales = pd.DataFrame(sales_orders)
            df_pos = pd.DataFrame(pos_orders)
            
            # Obtener información de partners usando método optimizado
            partners_dict = self._get_partners_info_batch(sales_orders + pos_orders)
            
            # Procesar líneas solo si se solicita
            all_lines = []
            if include_lines:
                print(f"📦 Procesando líneas de productos (batch_size: {batch_size})...")
                
                # Procesar líneas de ventas regulares con batch
                if not df_sales.empty:
                    all_lines.extend(self._process_sale_lines_batch(df_sales, batch_size))
                
                # Procesar líneas de POS con batch (si hay permisos)
                if not df_pos.empty:
                    all_lines.extend(self._process_pos_lines_batch(df_pos, batch_size))
                
                print(f"📋 Líneas procesadas: {len(all_lines)}")
            
            # Combinar los DataFrames de ventas y POS
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            df_lines = pd.DataFrame(all_lines)
            
            if not df.empty:
                # Procesar campos comunes
                df = self._transform_orders_data(df, partners_dict)
                
                print(f"✅ Total procesado: {len(df)} órdenes con {len(df_lines)} líneas")
                return {'orders': df, 'lines': df_lines}
            
            return {'orders': df, 'lines': df_lines}
            
        except Exception as e:
            return f"Error al leer las ventas entre {start_date} y {end_date}: {str(e)}"

    def _get_sales_orders_optimized(self, start_utc, end_utc, limit=None):
        """
        Versión optimizada para obtener órdenes de venta con menos campos
        
        :param start_utc: fecha inicio en UTC
        :param end_utc: fecha fin en UTC
        :param limit: límite de registros
        :return: lista de órdenes de venta optimizada
        """
        sales_domain = [
            ('state', 'in', ['sale', 'done']),
            ('invoice_status', '=', 'invoiced'),
            ('date_order', '>=', start_utc),
            ('date_order', '<=', end_utc)
        ]
        
        # Campos optimizados (solo lo esencial)
        sales_fields = [
            'name', 'date_order', 'partner_id', 'amount_total', 
            'state', 'user_id', 'team_id', 'order_line',
            'payment_term_id', 'warehouse_id'  # Agregados para term_name y warehouse_name
        ]
        
        params = {'fields': sales_fields, 'order': 'date_order DESC'}
        if limit:
            params['limit'] = limit
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'search_read',
            [sales_domain], params
        )
    
    def _get_pos_orders_optimized(self, start_utc, end_utc, limit=None):
        """
        Versión optimizada para obtener órdenes POS
        
        :param start_utc: fecha inicio en UTC
        :param end_utc: fecha fin en UTC
        :param limit: límite de registros
        :return: lista de órdenes POS optimizada
        """
        try:
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced']),
                ('date_order', '>=', start_utc),
                ('date_order', '<=', end_utc)
            ]
            
            # Campos optimizados para POS
            pos_fields = [
                'name', 'date_order', 'partner_id', 'amount_total',
                'state', 'user_id', 'lines'
            ]
            
            params = {'fields': pos_fields, 'order': 'date_order DESC'}
            if limit:
                params['limit'] = limit
            
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read',
                [pos_domain], params
            )
        except Exception as e:
            print(f"⚠️  Sin permisos para POS, continuando solo con ventas regulares: {str(e)[:100]}...")
            return []

    def _get_partners_info_batch(self, orders_list):
        """
        Versión optimizada que obtiene información de partners en batch
        
        :param orders_list: lista combinada de órdenes (sales + pos)
        :return: diccionario con información de partners
        """
        partner_ids = []
        for order in orders_list:
            if order.get('partner_id'):
                partner_ids.append(order['partner_id'][0])
        partner_ids = list(set(partner_ids))
        
        if partner_ids:
            # Obtener partners en una sola consulta
            partners = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'read',
                [partner_ids],
                {'fields': ['id', 'vat', 'l10n_latam_identification_type_id', 'name']}
            )
            return {p['id']: p for p in partners}
        return {}

    def _process_sale_lines_batch(self, df_sales, batch_size=500):
        """
        Procesa líneas de productos de órdenes de venta en lotes para mejor rendimiento
        
        :param df_sales: DataFrame con órdenes de venta
        :param batch_size: tamaño del lote para procesamiento
        :return: lista de líneas procesadas
        """
        all_lines = []
        if df_sales.empty:
            return all_lines
        
        # Recopilar todos los line_ids primero
        all_line_ids = []
        order_line_map = {}  # mapeo de line_id a order info
        
        for _, row in df_sales.iterrows():
            if row['order_line']:
                for line_id in row['order_line']:
                    all_line_ids.append(line_id)
                    order_line_map[line_id] = {
                        'order_name': row['name'],
                        'order_id': row.get('id', 0)
                    }
        
        if not all_line_ids:
            return all_lines
        
        # Procesar líneas en lotes
        for i in range(0, len(all_line_ids), batch_size):
            batch_line_ids = all_line_ids[i:i + batch_size]
            
            try:
                # Obtener detalles de las líneas en batch
                line_details = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'sale.order.line', 'read',
                    [batch_line_ids],
                    {'fields': [
                        'id', 'order_id', 'product_id', 'product_uom_qty',
                        'price_unit', 'price_subtotal', 'name'
                    ]}
                )
                
                # Recopilar todos los product_ids únicos del batch
                product_ids = []
                for line in line_details:
                    if line['product_id']:
                        product_ids.append(line['product_id'][0])
                product_ids = list(set(product_ids))
                
                # Obtener información de productos en batch
                if product_ids:
                    products_info = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'product.product', 'read',
                        [product_ids],
                        {'fields': ['id', 'default_code', 'name']}
                    )
                    products_dict = {p['id']: p for p in products_info}
                    
                    # Procesar líneas del batch
                    for line in line_details:
                        if line['product_id']:
                            product_info = products_dict.get(line['product_id'][0], {})
                            order_info = order_line_map.get(line['id'], {})
                            
                            line_data = {
                                'sale_order': order_info.get('order_name', ''),
                                'items_product_sku': product_info.get('default_code', ''),
                                'items_product_description': product_info.get('name', ''),
                                'items_quantity': line['product_uom_qty'],
                                'items_unitPrice': line['price_unit'],
                                'price_subtotal': line['price_subtotal']
                            }
                            all_lines.append(line_data)
                            
            except Exception as e:
                print(f"⚠️  Error procesando batch de líneas: {str(e)[:50]}...")
                continue
        
        return all_lines

    def _process_pos_lines_batch(self, df_pos, batch_size=500):
        """
        Procesa líneas de productos de órdenes POS en lotes
        
        :param df_pos: DataFrame con órdenes POS
        :param batch_size: tamaño del lote para procesamiento
        :return: lista de líneas procesadas
        """
        all_lines = []
        if df_pos.empty:
            return all_lines
        
        # Recopilar todos los line_ids primero
        all_line_ids = []
        order_line_map = {}
        
        for _, row in df_pos.iterrows():
            if row['lines']:
                for line_id in row['lines']:
                    all_line_ids.append(line_id)
                    order_line_map[line_id] = {
                        'order_name': row['name'],
                        'order_id': row.get('id', 0)
                    }
        
        if not all_line_ids:
            return all_lines
        
        # Procesar líneas en lotes
        for i in range(0, len(all_line_ids), batch_size):
            batch_line_ids = all_line_ids[i:i + batch_size]
            
            try:
                line_details = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'pos.order.line', 'read',
                    [batch_line_ids],
                    {'fields': [
                        'id', 'product_id', 'qty', 'price_unit',
                        'price_subtotal', 'name'
                    ]}
                )
                
                # Recopilar product_ids únicos del batch
                product_ids = []
                for line in line_details:
                    if line['product_id']:
                        product_ids.append(line['product_id'][0])
                product_ids = list(set(product_ids))
                
                # Obtener información de productos en batch
                if product_ids:
                    products_info = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'product.product', 'read',
                        [product_ids],
                        {'fields': ['id', 'default_code', 'name']}
                    )
                    products_dict = {p['id']: p for p in products_info}
                    
                    # Procesar líneas del batch
                    for line in line_details:
                        if line['product_id']:
                            product_info = products_dict.get(line['product_id'][0], {})
                            order_info = order_line_map.get(line['id'], {})
                            
                            line_data = {
                                'sale_order': order_info.get('order_name', ''),
                                'items_product_sku': product_info.get('default_code', ''),
                                'items_product_description': product_info.get('name', ''),
                                'items_quantity': line['qty'],
                                'items_unitPrice': line['price_unit'],
                                'price_subtotal': line['price_subtotal']
                            }
                            all_lines.append(line_data)
                            
            except Exception as e:
                print(f"⚠️  Error procesando batch de líneas POS: {str(e)[:50]}...")
                continue
        
        return all_lines

    def read_all_sales(self, limit=1000, offset=0, days_back=None, include_lines=True):
        """
        Lee ventas con filtros optimizados y opciones de rendimiento
        
        :param limit: Número máximo de registros (default: 1000)
        :param offset: Registros a saltar para paginación (default: 0)
        :param days_back: Días hacia atrás desde hoy (None = sin filtro, busca todas)
        :param include_lines: Si incluir líneas de productos (default: True para datos completos)
        :return: DataFrame con las ventas
        """
        try:
            if days_back is not None:
                print(f"🚀 Modo optimizado: últimos {days_back} días, límite {limit}, offset {offset}")
            else:
                print(f"🚀 Modo optimizado: todas las órdenes, límite {limit}, offset {offset}")
            print(f"📦 Líneas de productos: {'SÍ (completo)' if include_lines else 'NO (solo órdenes)'}")
            
            # 1. Obtener ventas usando versión optimizada
            sales_orders = self._get_all_sales_orders_optimized(limit, offset, days_back)
            pos_orders = self._get_all_pos_orders_optimized(limit, offset, days_back)
            
            print(f"📊 Órdenes obtenidas: {len(sales_orders)} ventas + {len(pos_orders)} POS")
            
            # Convertir a DataFrames
            df_sales = pd.DataFrame(sales_orders)
            df_pos = pd.DataFrame(pos_orders)
            
            # Obtener información de partners (solo para órdenes encontradas)
            partners_dict = self._get_partners_info(sales_orders + pos_orders)
            
            # Procesar líneas solo si se solicita
            all_lines = []
            if include_lines:
                print("📦 Procesando líneas de productos...")
                if not df_sales.empty:
                    all_lines.extend(self._process_sale_lines_batch(df_sales, 500))
                if not df_pos.empty:
                    all_lines.extend(self._process_pos_lines_batch(df_pos, 500))
                print(f"📋 Líneas procesadas: {len(all_lines)}")
            
            # Combinar DataFrames
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            df_lines = pd.DataFrame(all_lines)
            
            # Aplicar transformaciones
            if not df.empty:
                df = self._transform_orders_data(df, partners_dict)
            
            print(f"✅ Total procesado: {len(df)} órdenes")
            return {'orders': df, 'lines': df_lines}
            
        except Exception as e:
            return f"Error al leer ventas: {str(e)}"
    
    def read_all_sales_summary(self, days_back=None):
        """
        Resumen ejecutivo rápido de ventas sin procesar líneas de productos
        
        :param days_back: Días hacia atrás desde hoy (None = todas las órdenes)
        :return: Resumen básico de ventas
        """
        try:
            # Solo campos básicos, sin líneas
            sales_domain = [
                ('state', 'in', ['sale', 'done']),
                ('invoice_status', '=', 'invoiced'),  # Solo órdenes completamente facturadas
            ]
            
            # Agregar filtro por fecha solo si se especifica days_back
            if days_back is not None:
                sales_domain.append(('date_order', '>=', (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')))
            
            basic_fields = ['name', 'date_order', 'partner_id', 'amount_total', 'state']
            
            sales = self.models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [sales_domain],
                {'fields': basic_fields, 'order': 'date_order DESC'}
            )
            
            df = pd.DataFrame(sales)
            
            if not df.empty:
                # Estadísticas rápidas
                stats = {
                    'total_orders': len(df),
                    'total_amount': df['amount_total'].sum(),
                    'avg_order_value': df['amount_total'].mean(),
                    'date_range': f"{df['date_order'].min()} a {df['date_order'].max()}",
                    'top_amounts': df.nlargest(5, 'amount_total')[['name', 'amount_total']].to_dict('records')
                }
                
                if days_back is not None:
                    print(f"📊 Resumen últimos {days_back} días:")
                else:
                    print(f"📊 Resumen todas las órdenes:")
                print(f"   Total órdenes: {stats['total_orders']}")
                print(f"   Monto total: ${stats['total_amount']:,.0f}")
                print(f"   Valor promedio: ${stats['avg_order_value']:,.0f}")
                
                return {'summary': stats, 'orders': df}
            
            return {'summary': {}, 'orders': df}
            
        except Exception as e:
            return f"Error al generar resumen: {str(e)}"

    def read_all_sales_lazy(self, limit=1000, offset=0, days_back=None):
        """
        Versión lazy: obtiene órdenes SIN líneas de productos para máxima velocidad
        (ej: dashboards, conteos rápidos, análisis de clientes)
        
        :param limit: Número máximo de registros (default: 1000)
        :param offset: Registros a saltar para paginación (default: 0)
        :param days_back: Días hacia atrás desde hoy (None = sin filtro, busca todas)
        :return: DataFrame con solo órdenes (sin líneas de productos)
        """
        try:
            if days_back is not None:
                print(f"⚡ Modo lazy: últimos {days_back} días, límite {limit}, SIN líneas de productos")
            else:
                print(f"⚡ Modo lazy: todas las órdenes, límite {limit}, SIN líneas de productos")
            
            # Obtener órdenes usando versión optimizada
            sales_orders = self._get_all_sales_orders_optimized(limit, offset, days_back)
            pos_orders = self._get_all_pos_orders_optimized(limit, offset, days_back)
            
            print(f"📊 Órdenes obtenidas: {len(sales_orders)} ventas + {len(pos_orders)} POS")
            
            # Convertir a DataFrames
            df_sales = pd.DataFrame(sales_orders)
            df_pos = pd.DataFrame(pos_orders)
            
            # Obtener información de partners
            partners_dict = self._get_partners_info(sales_orders + pos_orders)
            
            # Combinar DataFrames (SIN procesar líneas)
            df = pd.concat([df_sales, df_pos], ignore_index=True)
            
            # Aplicar transformaciones
            if not df.empty:
                df = self._transform_orders_data(df, partners_dict)
            
            print(f"⚡ Total procesado: {len(df)} órdenes (modo lazy sin líneas)")
            return {'orders': df, 'lines': pd.DataFrame()}  # DataFrame vacío para líneas
            
        except Exception as e:
            return f"Error al leer ventas lazy: {str(e)}"
