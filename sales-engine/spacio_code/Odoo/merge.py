import pandas as pd

# Rutas de los archivos
historic_orders = '/home/snparada/Spacionatural/Data/Historical/historic_orders_laudus_with_items.csv'
sales_all_time = '/home/snparada/Spacionatural/Data/Historical/Finance/sales_all_time.csv'
output_path = '/home/snparada/Spacionatural/Data/Historical/Finance/historic_sales_with_items.csv'

# Leer los archivos CSV
df_orders = pd.read_csv(historic_orders, low_memory=False)
df_sales = pd.read_csv(sales_all_time, low_memory=False)

# Mostrar información sobre los DataFrames originales
print(f"Registros en df_orders: {len(df_orders)}")
print(f"Registros en df_sales: {len(df_sales)}")

# Concatenar los dataframes
combined_df = pd.concat([df_orders, df_sales], axis=0, ignore_index=True)

# Mostrar información sobre el resultado
print(f"Registros en combined_df: {len(combined_df)}")

# Guardar el resultado en un nuevo archivo CSV
combined_df.to_csv(output_path, index=False)
print(f"\nArchivo guardado exitosamente en: {output_path}")
