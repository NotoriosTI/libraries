import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
from odoo_lib.sales import OdooSales
import pandas as pd
from datetime import datetime, timedelta

def main():
    # Inicializar la conexión con Odoo
    odoo_sales = OdooSales()
    
    # Leer el archivo histórico
    historic_file = '/home/snparada/Spacionatural/Data/Historical/Finance/historic_sales_with_items.csv'
    historic_df = pd.read_csv(historic_file, low_memory=False)
    
    # Obtener la última fecha del archivo histórico
    # Primero convertimos la columna issuedDate a datetime
    historic_df['issuedDate'] = pd.to_datetime(historic_df['issuedDate'])
    last_date = historic_df['issuedDate'].max().date()
    
    # Calcular el día siguiente
    next_day = last_date + timedelta(days=1)
    today = datetime.today().date()
    
    # Si hay días futuros, extraer las ventas
    if next_day <= today:
        result = odoo_sales.read_sales_by_date_range(next_day, today)
        
        if isinstance(result, dict):
            # Obtener los DataFrames
            orders_df = result['orders']
            lines_df = result['lines']
            
            # Crear el DataFrame final con el formato requerido
            final_rows = []
            
            # Para cada orden
            for _, order in orders_df.iterrows():
                # Obtener las líneas de esta orden
                order_lines = lines_df[lines_df['sale_order'] == order['docnumber']]
                
                # Para cada línea de la orden
                for _, line in order_lines.iterrows():
                    row = {
                        'salesInvoiceId': order['salesInvoiceId'],
                        'doctype_name': 'Factura',
                        'docnumber': order['docnumber'],
                        'customer_customerid': order['customer_customerid'],
                        'customer_name': order['customer_name'],
                        'customer_vatid': order['customer_vatid'],
                        'salesman_name': order['salesman_name'],
                        'term_name': None,
                        'warehouse_name': None,
                        'totals_net': order['totals_net'],
                        'totals_vat': order['totals_vat'],
                        'total_total': order['total_total'],
                        'items_product_description': line['items_product_description'],
                        'items_product_sku': line['items_product_sku'],
                        'items_quantity': line['items_quantity'],
                        'items_unitPrice': line['items_unitPrice'],
                        'issuedDate': pd.to_datetime(order['issuedDate']).strftime('%Y-%m-%d'),
                        'sales_channel': order['sales_channel']
                    }
                    final_rows.append(row)
            
            # Crear el DataFrame final
            final_df = pd.DataFrame(final_rows)
            
            # Asegurarnos de que las fechas en historic_df estén en el formato correcto
            historic_df['issuedDate'] = historic_df['issuedDate'].dt.strftime('%Y-%m-%d')
            
            # Concatenar con el histórico y eliminar duplicados
            combined_df = pd.concat([historic_df, final_df], axis=0, ignore_index=True)
            # Eliminar duplicados considerando todas las columnas
            combined_df = combined_df.drop_duplicates()
            
            # Guardar el resultado
            combined_df.to_csv(historic_file, index=False)
            
            print(f"Registros antes de la actualización: {len(historic_df)}")
            print(f"Registros después de la actualización: {len(combined_df)}")

            
        else:
            print(f"Error al extraer las ventas: {result}")
    else:
        print("No hay nuevos datos para extraer")

if __name__ == "__main__":
    main()
