#!/usr/bin/env python3
"""
Test simple para verificar get_stock_by_sku con SKU 6995
Incluye verificación de la nueva funcionalidad UOM
"""

import sys
import os

# Agregar el directorio src al path para importar el módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from odoo_api.warehouses import OdooWarehouse
from pprint import pprint

# Importar configuración
from config_manager import secrets

def test_sku_6995():
    """
    Test para verificar que get_stock_by_sku funciona correctamente con SKU 6995
    """
    print("=" * 60)
    print("TEST: get_stock_by_sku con SKU 6995")
    print("=" * 60)
    
    try: 
        # Inicializar la conexión con Odoo
        warehouse = OdooWarehouse(
            db=secrets.ODOO_PROD_DB,
            url=secrets.ODOO_PROD_URL,
            username=secrets.ODOO_PROD_USERNAME,
            password=secrets.ODOO_PROD_PASSWORD
        )
        
        print("✅ Conexión a Odoo establecida")
        
        # Test 1: Consulta individual del SKU 6995
        print("\n" + "-" * 40)
        print("TEST 1: Consulta individual del SKU 6995")
        print("-" * 40)
        
        result_single = warehouse.get_stock_by_sku("6995")
        
        # Verificaciones
        if result_single.get("found"):
            print("\n✅ Producto encontrado")
            print(f"   - Nombre: {result_single.get('product_name')}")
            print(f"   - SKU: {result_single.get('sku')}")
            print(f"   - UOM: {result_single.get('uom')}")
            print(f"   - Stock disponible: {result_single.get('qty_available')}")
            print(f"   - Stock virtual: {result_single.get('virtual_available')}")
            print(f"   - Ubicaciones con stock: {len(result_single.get('locations', []))}")
            
            # Mostrar ubicaciones si existen
            if result_single.get('locations'):
                print("\n   Ubicaciones con stock:")
                for location in result_single['locations']:
                    print(f"     - {location['location']}: {location['available']} disponibles")
        else:
            print("\n❌ Producto no encontrado")
            if "error" in result_single:
                print(f"   - Error: {result_single.get('error')}")
        
        # Test 2: Consulta batch con múltiples SKUs (incluyendo 6995)
        print("\n" + "-" * 40)
        print("TEST 2: Consulta batch con múltiples SKUs")
        print("-" * 40)
        
        result_batch = warehouse.get_stock_by_sku(["6995", "5959", "1111"])
        
        print("Resultado de consulta batch:")
        pprint(result_batch)
        
        # Verificaciones del batch
        print("\nVerificaciones del procesamiento batch:")
        for sku in ["6995", "5959", "1111"]:
            if sku in result_batch:
                result = result_batch[sku]
                if result.get("found"):
                    print(f"✅ {sku}: Encontrado - UOM: {result.get('uom')} - Stock: {result.get('qty_available')}")
                else:
                    print(f"❌ {sku}: No encontrado")
            else:
                print(f"❌ {sku}: No procesado")
        
        # Test 3: Verificar estructura de respuesta
        print("\n" + "-" * 40)
        print("TEST 3: Verificación de estructura de respuesta")
        print("-" * 40)
        
        if result_single.get("found"):
            required_fields = ["qty_available", "virtual_available", "locations", "product_name", "sku", "found", "uom"]
            missing_fields = []
            
            for field in required_fields:
                if field not in result_single:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ Campos faltantes: {missing_fields}")
            else:
                print("✅ Todos los campos requeridos están presentes")
                
                # Verificar tipos de datos
                print("\nVerificación de tipos de datos:")
                print(f"   - qty_available: {type(result_single['qty_available'])} = {result_single['qty_available']}")
                print(f"   - virtual_available: {type(result_single['virtual_available'])} = {result_single['virtual_available']}")
                print(f"   - locations: {type(result_single['locations'])} = {len(result_single['locations'])} elementos")
                print(f"   - product_name: {type(result_single['product_name'])} = {result_single['product_name']}")
                print(f"   - sku: {type(result_single['sku'])} = {result_single['sku']}")
                print(f"   - found: {type(result_single['found'])} = {result_single['found']}")
                print(f"   - uom: {type(result_single['uom'])} = {result_single['uom']}")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETADO")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante el test: {str(e)}")
        print("Asegúrate de configurar correctamente los parámetros de conexión a Odoo")
        return False

if __name__ == "__main__":
    # Ejecutar el test
    success = test_sku_6995()
    
    if success:
        print("\n🎉 Test completado exitosamente!")
    else:
        print("\n💥 Test falló!")
        sys.exit(1) 