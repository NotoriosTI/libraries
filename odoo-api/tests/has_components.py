from odoo_api.product import OdooProduct
from odoo_api.warehouses import OdooWarehouse
from config_manager import secrets

odoo_warehouse = OdooWarehouse(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
)

odoo_product = OdooProduct(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
)

# Test con los SKUs de tu ejemplo original
test_skus = ['8053', '9112', '5820', '5959', '7411', '7423', '7417', '6473', '7413', '6919']

print("=== TEST DE CAPACIDAD DE PRODUCCIÓN ===")
max_production = odoo_warehouse.get_max_production_quantity(test_skus)
print(f"Resultados: {max_production}")

print("\n=== ANÁLISIS DETALLADO ===")
for sku, max_qty in max_production.items():
    if max_qty > 0:
        print(f"✅ SKU {sku}: Puede producir {max_qty} unidades (tiene BOM)")
    else:
        print(f"❌ SKU {sku}: No puede producirse (sin BOM o sin componentes)")
        
        # Verificar si tiene stock disponible
        stock_info = odoo_warehouse.get_stock_by_sku(sku)
        if stock_info and stock_info.get('found'):
            available = stock_info.get('qty_available', 0)
            print(f"   📦 Stock disponible: {available} unidades")
        else:
            print(f"   📦 Producto no encontrado en inventario")

print("\n=== PRUEBA ADICIONAL CON SKUs CONOCIDOS ===")
additional_test = odoo_warehouse.get_max_production_quantity(['5959', '6211'])
print(f"SKUs adicionales: {additional_test}")