from src.odoo_api.product import OdooProduct
from src.odoo_api.warehouses import OdooWarehouse

odoo_product = OdooProduct(
    database="test", 
    dotenv_path="/Users/bastianibanez/work/libraries/odoo-api/.env"
    )



resultados = odoo_product.get_skus_by_name_flexible("aceite de argan")
for i, (nombre, sku) in enumerate(resultados[:]):
    var_attrs = odoo_product.get_variant_attributes_by_sku(sku)
    resultados[i] = (nombre, sku, var_attrs)
    print(f"Nombre: {nombre} | SKU: {sku} | Formato: {var_attrs}")
