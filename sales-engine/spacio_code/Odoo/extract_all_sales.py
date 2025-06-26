import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
from odoo_lib.sales import OdooSales
import pandas as pd

def main():
    # Inicializar la conexión con Odoo
    odoo_sales = OdooSales()
    
    # Extraer todas las ventas
    result = odoo_sales.read_all_sales()
    
    if isinstance(result, dict):
        output_file = '/home/snparada/Spacionatural/Data/Historical/Finance/sales_all_time.csv'
        
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
                    'issuedDate': order['issuedDate'],
                    'sales_channel': order['sales_channel']
                }
                final_rows.append(row)
        
        # Crear el DataFrame final
        final_df = pd.DataFrame(final_rows)
        
        # Definir el orden exacto de las columnas
        columns_order = [
            'salesInvoiceId',
            'doctype_name',
            'docnumber',
            'customer_customerid',
            'customer_name',
            'customer_vatid',
            'salesman_name',
            'term_name',
            'warehouse_name',
            'totals_net',
            'totals_vat',
            'total_total',
            'items_product_description',
            'items_product_sku',
            'items_quantity',
            'items_unitPrice',
            'issuedDate',
            'sales_channel'
        ]
        
        # Reordenar las columnas
        final_df = final_df[columns_order]
        
        # Guardar el resultado
        final_df.to_csv(output_file, index=False)
        
        print(f"Se han extraído {len(final_df)} líneas de productos de {len(orders_df)} ventas y guardado en {output_file}")
        print("\nPrimeras filas del archivo:")
        print(final_df.head())
        
    else:
        print(f"Error al extraer las ventas: {result}")

if __name__ == "__main__":
    main()
