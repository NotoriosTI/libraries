import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
from odoo_lib.warehouses import OdooWarehouse
import pandas as pd

warehouse = OdooWarehouse()
df_inventory = warehouse.read_stock_by_location()

# Crear una nueva columna que combine el warehouse y location
df_inventory['warehouse_location'] = df_inventory['location']

df_inventory['warehouse_location'] = df_inventory['warehouse_location'].replace({
    'Francisco de Villagra': 'FV',
    'Juan Sabaj': 'JS'
}, regex=True)

# Pivotear el DataFrame para tener las columnas como warehouse/location y los valores como el stock
df_pivot = df_inventory.pivot_table(index=['internal_reference', 'product_id','tags'], 
                                    columns='warehouse_location', 
                                    values='quantity', 
                                    aggfunc='sum', 
                                    fill_value=0).reset_index()


df_pivot.to_csv('/home/snparada/Spacionatural/Data/Recent/stocks_by_location.csv', index=False)