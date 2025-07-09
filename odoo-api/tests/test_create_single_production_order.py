import sys
import pandas as pd
from pprint import pprint
from src.odoo_api.product import OdooProduct
from config_manager import secrets

# Configuración de conexión (ajusta estos valores a tu entorno real)
DB = secrets.ODOO_PROD_DB
URL = secrets.ODOO_PROD_URL
USER = secrets.ODOO_PROD_USERNAME
PASSWORD = secrets.ODOO_PROD_PASSWORD

# Instancia de OdooProduct
odoo = OdooProduct(db=DB, url=URL, username=USER, password=PASSWORD)

# SKUs válidos proporcionados
skus = [
    {'SKU': '6211', 'TOTAL PRODUCCIÓN': 10, 'A PRODUCIR PICKING (1 MES)': 2},
    {'SKU': '7432', 'TOTAL PRODUCCIÓN': 5, 'A PRODUCIR PICKING (1 MES)': 1},
    {'SKU': '9067', 'TOTAL PRODUCCIÓN': 8, 'A PRODUCIR PICKING (1 MES)': 3},
    {'SKU': '8526', 'TOTAL PRODUCCIÓN': 15, 'A PRODUCIR PICKING (1 MES)': 5},
]

def test_create_single_production_order():
    for sku_data in skus:
        df_orden = pd.Series(sku_data)
        result = odoo.create_single_production_order(df_orden)
        pprint(result, indent=2)
        assert isinstance(result, dict), 'El resultado debe ser un diccionario.'
        assert 'status' in result, 'El resultado debe tener la clave status.'
        assert result['status'] == 'success', f"La orden de producción no fue creada correctamente para SKU {sku_data['SKU']}: {result.get('message')}"
        assert 'production_order_id' in result, 'Debe retornar el id de la orden de producción.'

if __name__ == '__main__':
    try:
        test_create_single_production_order()
        print('\nTodos los tests pasaron correctamente.')
    except AssertionError as e:
        print(f'Fallo en el test: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'Error inesperado: {e}')
        sys.exit(2) 