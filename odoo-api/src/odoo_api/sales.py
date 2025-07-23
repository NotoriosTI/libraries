from datetime import datetime, timedelta
from .api import OdooAPI
import pandas as pd
import pytz

class OdooSales(OdooAPI):
    """
    Clase para manejar operaciones relacionadas con ventas en Odoo.
    Refactored to handle data fetching and preparation in one place.
    """
    def __init__(self, db=None, url=None, username=None, password=None) -> None:
        super().__init__(db=db, url=url, username=username, password=password)
        self._user_timezone = None

    def get_user_timezone(self) -> str:
        """Obtiene la zona horaria del usuario actual (por defecto Santiago)."""
        if self._user_timezone is None:
            try:
                user_info = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'res.users', 'read', [self.uid], {'fields': ['tz']}
                )[0]
                self._user_timezone = user_info.get('tz', 'America/Santiago')
            except:
                self._user_timezone = 'America/Santiago'
        return self._user_timezone

    def _convert_timezone_range(self, start_date, end_date, user_timezone) -> tuple[str, str]:
        """Convierte un rango de fechas en zona horaria local a rango UTC."""
        local_tz = pytz.timezone(user_timezone)
        utc_tz = pytz.UTC
        local_start = local_tz.localize(datetime.combine(start_date, datetime.min.time()))
        local_end = local_tz.localize(datetime.combine(end_date, datetime.max.time()))
        utc_start = local_start.astimezone(utc_tz).strftime('%Y-%m-%d %H:%M:%S')
        utc_end = local_end.astimezone(utc_tz).strftime('%Y-%m-%d %H:%M:%S')
        return utc_start, utc_end

    def _get_sales_orders(self, start_utc, end_utc, limit=None) -> list[dict]:
        """Helper to get sales orders."""
        sales_domain = [
            ('state', 'in', ['sale', 'done']),
            ('invoice_status', '=', 'invoiced'),
            ('date_order', '>=', start_utc),
            ('date_order', '<=', end_utc)
        ]
        sales_fields = [
            'id', 'name', 'date_order', 'partner_id', 'amount_total',
            'user_id', 'team_id', 'order_line', 'payment_term_id', 'warehouse_id'
        ]
        params = {'fields': sales_fields, 'order': 'date_order DESC'}
        if limit:
            params['limit'] = limit
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'search_read', [sales_domain], params
        )

    def _get_pos_orders(self, start_utc, end_utc, limit=None) -> list[dict]:
        """Helper to get POS orders."""
        try:
            pos_domain = [
                ('state', 'in', ['paid', 'done', 'invoiced']),
                ('date_order', '>=', start_utc),
                ('date_order', '<=', end_utc)
            ]
            pos_fields = [
                'id', 'name', 'date_order', 'partner_id', 'amount_total',
                'user_id', 'lines'
            ]
            params = {'fields': pos_fields, 'order': 'date_order DESC'}
            if limit:
                params['limit'] = limit
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                'pos.order', 'search_read', [pos_domain], params
            )
        except Exception as e:
            print(f"⚠️  Sin permisos para POS, continuando solo con ventas regulares: {str(e)[:100]}...")
            return []

    def _process_lines_in_batch(self, line_ids, model_name, fields, product_key_map, batch_size=500) -> list[dict]:
        """Generic helper to process order lines in batches."""
        all_lines_data = []
        if not line_ids:
            return all_lines_data

        for i in range(0, len(line_ids), batch_size):
            batch_line_ids = [line['id'] for line in line_ids[i:i + batch_size]]
            line_details = self.models.execute_kw(
                self.db, self.uid, self.password, model_name, 'read', [batch_line_ids], {'fields': fields}
            )

            product_ids = [line['product_id'][0] for line in line_details if line.get('product_id')]
            if not product_ids:
                continue

            products_info = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.product', 'read', [list(set(product_ids))], {'fields': ['id', 'default_code', 'name']}
            )
            products_dict = {p['id']: p for p in products_info}

            for line in line_details:
                if line.get('product_id'):
                    product_info = products_dict.get(line['product_id'][0], {})
                    line_data = {
                        'order_id': line['order_id'][0] if line.get('order_id') else product_key_map.get(line['id']),
                        'items_product_sku': product_info.get('default_code', ''),
                        'items_product_description': product_info.get('name', ''),
                        'items_quantity': line.get('product_uom_qty') or line.get('qty', 0),
                        'items_unitprice': line.get('price_unit', 0.0),
                    }
                    all_lines_data.append(line_data)
        return all_lines_data

    def read_sales_by_date_range(self, start_date, end_date, limit=None) -> pd.DataFrame:
        """
        Lee las ventas, las procesa y devuelve un DataFrame único y limpio,
        listo para ser insertado en la base de datos.

        Esta función ahora maneja toda la lógica:
        1.  Obtiene órdenes de Venta y POS.
        2.  Obtiene todas las líneas de productos en lotes.
        3.  Combina y transforma los datos en un DataFrame final.
        4.  Devuelve un único DataFrame listo para el upsert.

        :param start_date: datetime.date inicio del rango
        :param end_date: datetime.date fin del rango
        :param limit: Límite de órdenes a procesar (None = sin límite)
        :return: DataFrame único y combinado o un DataFrame vacío.
        """
        try:
            # --- 1. Fetch Raw Data ---
            user_tz = self.get_user_timezone()
            start_utc, end_utc = self._convert_timezone_range(start_date, end_date, user_tz)

            sales_orders = self._get_sales_orders_optimized(start_utc, end_utc, limit)
            pos_orders = self._get_pos_orders_optimized(start_utc, end_utc, limit)
            all_orders = sales_orders + pos_orders
            
            if not all_orders:
                print("✅ No se encontraron órdenes en el rango de fechas.")
                return pd.DataFrame()

            df_orders = pd.DataFrame(all_orders)

            # --- 2. Process Lines in Batch ---
            sales_line_keys = [{'id': l_id, 'order_id': o['id']} for o in sales_orders for l_id in o['order_line']]
            pos_line_keys = [{'id': l_id, 'order_id': o['id']} for o in pos_orders for l_id in o['lines']]
            
            # Mapping for POS lines which don't have a direct order_id reference
            pos_line_to_order_map = {item['id']: item['order_id'] for item in pos_line_keys}

            sales_lines = self._process_lines_in_batch(sales_line_keys, 'sale.order.line', ['order_id', 'product_id', 'product_uom_qty', 'price_unit'], {})
            pos_lines = self._process_lines_in_batch(pos_line_keys, 'pos.order.line', ['product_id', 'qty', 'price_unit'], pos_line_to_order_map)

            if not sales_lines and not pos_lines:
                print("⚠️  No se encontraron líneas de productos para las órdenes.")
                return pd.DataFrame()

            df_lines = pd.DataFrame(sales_lines + pos_lines)

            # --- 3. Merge and Transform into a Single DataFrame ---
            # Rename order 'id' to 'order_id' to prepare for merge
            df_orders.rename(columns={'id': 'order_id'}, inplace=True)
            
            # Merge orders with their lines
            df_final = pd.merge(df_orders, df_lines, on='order_id', how='inner')

            # --- 4. Final Data Structuring and Cleaning (Single Pass) ---
            # Get partner info in a single batch
            partner_ids = [p[0] for p in df_final['partner_id'] if isinstance(p, (list, tuple))]
            partners_info = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'read', [list(set(partner_ids))], {'fields': ['id', 'vat']}
            )
            partners_dict = {p['id']: p for p in partners_info}

            # Apply transformations
            df_final['salesinvoiceid'] = df_final['name']
            df_final['docnumber'] = df_final['name']
            df_final['doctype_name'] = 'Factura'
            df_final['issueddate'] = pd.to_datetime(df_final['date_order']).dt.date
            
            df_final['customer_customerid'] = df_final['partner_id'].apply(lambda x: x[0] if isinstance(x, (list, tuple)) else None)
            df_final['customer_name'] = df_final['partner_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
            df_final['customer_vatid'] = df_final['customer_customerid'].apply(lambda x: partners_dict.get(x, {}).get('vat', ''))
            
            df_final['salesman_name'] = df_final['user_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
            df_final['term_name'] = df_final['payment_term_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
            df_final['warehouse_name'] = df_final['warehouse_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else None)
            
            df_final['totals_net'] = (df_final['amount_total'] / 1.19).round(2)
            df_final['totals_vat'] = (df_final['amount_total'] - df_final['totals_net']).round(2)
            df_final['total_total'] = df_final['amount_total']
            
            df_final['sales_channel'] = df_final.apply(lambda row: 'Tienda Sabaj' if 'Juan Sabaj' in str(row.get('name')) else (row['team_id'][1] if isinstance(row.get('team_id'), list) else 'Otro'), axis=1)

            # --- 5. Return Final, Clean DataFrame ---
            # Select and order the final columns
            final_columns = [
                'salesinvoiceid', 'doctype_name', 'docnumber', 'customer_customerid',
                'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
                'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
                'items_product_description', 'items_product_sku', 'items_quantity',
                'items_unitprice', 'issueddate', 'sales_channel'
            ]
            
            return df_final[final_columns]

        except Exception as e:
            print(f"❌ Error fatal al procesar ventas: {str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame() # Return an empty frame on failure