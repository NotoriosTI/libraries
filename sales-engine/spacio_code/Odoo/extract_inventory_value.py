import sys
import pandas as pd
from datetime import datetime
import os
sys.path.append("/home/snparada/Spacionatural/Libraries/")

from odoo_lib.accountability import OdooAccountability

def get_accounts_sum():
    print("Iniciando conexión con Odoo...")
    accountability = OdooAccountability()
    
    # Leer saldos de las cuentas
    print("\nIntentando leer cuenta 1109001...")
    account_1 = accountability.read_account_balance("1109001")
    print(f"Resultado cuenta 1109001: {account_1}")
    
    print("\nIntentando leer cuenta 1109003...")
    account_2 = accountability.read_account_balance("1109003")
    print(f"Resultado cuenta 1109003: {account_2}")
    
    # Verificar que ambas cuentas existan
    if isinstance(account_1, str):
        print(f"\nError en cuenta 1109001: {account_1}")
        return
    if isinstance(account_2, str):
        print(f"\nError en cuenta 1109003: {account_2}")
        return
    
    # Sumar los saldos
    total_balance = account_1['balance'] + account_2['balance']
    
    print(f"\nSaldo cuenta 1109001: {account_1['balance']:,.2f}")
    print(f"Saldo cuenta 1109003: {account_2['balance']:,.2f}")
    print(f"Suma total: {total_balance:,.2f}")
    
    # Guardar en CSV
    save_to_csv(account_1['balance'], account_2['balance'], total_balance)
    
    return total_balance

def save_to_csv(saldo_1, saldo_2, total):
    csv_path = "/home/snparada/Spacionatural/Data/Historical/Finance/inventory_value_in_time.csv"
    today = datetime.now().date()
    
    # Crear el directorio si no existe
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    # Preparar los nuevos datos
    new_data = pd.DataFrame({
        'fecha': [today],
        'saldo_1109001': [saldo_1],
        'saldo_1109003': [saldo_2],
        'total': [total]
    })
    
    try:
        # Intentar leer el CSV existente
        if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
            df = pd.read_csv(csv_path)
            # Convertir la columna fecha a datetime
            df['fecha'] = pd.to_datetime(df['fecha']).dt.date
        else:
            # Crear un DataFrame vacío con los mismos tipos de datos que new_data
            df = pd.DataFrame(columns=new_data.columns).astype(new_data.dtypes)
        
        # Verificar si ya existe un registro para hoy
        if today in df['fecha'].values:
            print(f"\nYa existe un registro para la fecha {today}. No se guardará el dato.")
            return
        
        # Agregar los nuevos datos
        df = pd.concat([df, new_data], ignore_index=True)
        
        # Ordenar por fecha
        df = df.sort_values('fecha')
        
        # Guardar el CSV
        df.to_csv(csv_path, index=False)
        print(f"\nDatos guardados exitosamente en {csv_path}")
        
    except Exception as e:
        print(f"\nError al guardar los datos: {str(e)}")

if __name__ == "__main__":
    get_accounts_sum()
