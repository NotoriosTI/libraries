from odoo_api import OdooProduct
from config_manager import secrets
import sys

# Redirigir stdout a un archivo para capturar los prints
original_stdout = sys.stdout
with open('debug_batch.log', 'w') as f:
    sys.stdout = f
    
    SKUS = ["6256", "8085", "6009", "6995"]
    
    odoo_db = secrets.ODOO_PROD_DB
    odoo_user = secrets.ODOO_PROD_USERNAME
    odoo_password = secrets.ODOO_PROD_PASSWORD
    odoo_url = secrets.ODOO_PROD_URL
    
    product_api = OdooProduct(db=odoo_db, url=odoo_url, username=odoo_user, password=odoo_password)
    
    print("=== DEBUG BATCH PROCESSING ===")
    
    # Test individual first
    print("\n--- Individual Processing ---")
    individual_results = {}
    for sku in SKUS:
        print(f"\nProcessing SKU: {sku}")
        result = product_api.get_variant_attributes_by_sku(sku)
        individual_results[sku] = result
        print(f"Result: {result}")
    
    # Test batch
    print("\n--- Batch Processing ---")
    print(f"SKUs to process: {SKUS}")
    print(f"Type of SKUS: {type(SKUS)}")
    print(f"Length of SKUS: {len(SKUS)}")
    
    # Debug the function call
    print(f"Calling get_variant_attributes_by_sku with type: {type(SKUS)}")
    batch_result = product_api.get_variant_attributes_by_sku(SKUS)
    print(f"Batch result type: {type(batch_result)}")
    print(f"Batch result: {batch_result}")
    
    # Compare
    print("\n--- Comparison ---")
    print(f"Individual results: {individual_results}")
    print(f"Batch results: {batch_result}")
    print(f"Results match: {individual_results == batch_result}")
    
    # Test with single SKU in list
    print("\n--- Single SKU in List Test ---")
    single_sku_list = ["6256"]
    print(f"Testing with single SKU list: {single_sku_list}")
    single_result = product_api.get_variant_attributes_by_sku(single_sku_list)
    print(f"Single SKU list result type: {type(single_result)}")
    print(f"Single SKU list result: {single_result}")

# Restaurar stdout
sys.stdout = original_stdout
print("Debug completado. Revisa el archivo 'debug_batch.log'") 