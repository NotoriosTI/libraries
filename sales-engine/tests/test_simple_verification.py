#!/usr/bin/env python3
"""
Script de verificación simple para las mejoras implementadas.
Verifica que los cambios en el código estén presentes sin ejecutar la lógica completa.
"""

import os
import sys

def test_odoo_api_changes():
    """Verifica que se hayan agregado los campos necesarios en odoo-api"""
    print("\n🔍 Verificando cambios en odoo-api/src/odoo_api/sales.py...")
    
    odoo_api_path = os.path.join('..', 'odoo-api', 'src', 'odoo_api', 'sales.py')
    
    if not os.path.exists(odoo_api_path):
        print(f"❌ No se encuentra el archivo: {odoo_api_path}")
        return False
    
    try:
        with open(odoo_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar que se agregaron los campos payment_term_id y warehouse_id
        checks = [
            ('payment_term_id', 'payment_term_id' in content),
            ('warehouse_id', 'warehouse_id' in content),
            ('doctype_name = "Factura"', '"Factura"' in content),
            ('term_name mapping', 'term_name' in content),
            ('warehouse_name mapping', 'warehouse_name' in content)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'ENCONTRADO' if passed else 'FALTANTE'}")
            if not passed:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

def test_database_schema_definition():
    """Verifica la definición del esquema de la base de datos"""
    print("\n🗄️  Verificando esquema de base de datos en utils.py...")
    
    utils_path = os.path.join('src', 'sales_engine', 'utils.py')
    
    if not os.path.exists(utils_path):
        print(f"❌ No se encuentra el archivo: {utils_path}")
        return False
    
    try:
        with open(utils_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar que todas las columnas esperadas estén en la definición
        expected_columns = [
            'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
            'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
            'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
            'items_product_description', 'items_product_sku', 'items_quantity',
            'items_unitPrice', 'issuedDate', 'sales_channel', 'created_at', 'updated_at'
        ]
        
        all_found = True
        for column in expected_columns:
            if column in content:
                print(f"   ✅ {column}: ENCONTRADO")
            else:
                print(f"   ❌ {column}: FALTANTE")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

def test_db_updater_columns():
    """Verifica que db_updater tenga las columnas correctas"""
    print("\n🔄 Verificando columnas en db_updater.py...")
    
    db_updater_path = os.path.join('src', 'sales_engine', 'db_updater.py')
    
    if not os.path.exists(db_updater_path):
        print(f"❌ No se encuentra el archivo: {db_updater_path}")
        return False
    
    try:
        with open(db_updater_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar que las columnas estén en la función bulk_load_data
        critical_columns = ['term_name', 'warehouse_name', 'doctype_name']
        
        all_found = True
        for column in critical_columns:
            if column in content:
                print(f"   ✅ {column}: ENCONTRADO en db_updater")
            else:
                print(f"   ❌ {column}: FALTANTE en db_updater")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

def test_sales_integration_mapping():
    """Verifica el mapeo en sales_integration.py"""
    print("\n🗺️  Verificando mapeo en sales_integration.py...")
    
    integration_path = os.path.join('src', 'sales_engine', 'sales_integration.py')
    
    if not os.path.exists(integration_path):
        print(f"❌ No se encuentra el archivo: {integration_path}")
        return False
    
    try:
        with open(integration_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar el mapeo de columnas
        mappings_to_check = [
            ('payment_term_name', 'term_name'),
            ('warehouse_name', 'warehouse_name'),
            ('doctype_name', 'Factura')
        ]
        
        all_found = True
        for mapping_key, mapping_value in mappings_to_check:
            if mapping_key in content and mapping_value in content:
                print(f"   ✅ Mapeo {mapping_key} -> {mapping_value}: ENCONTRADO")
            else:
                print(f"   ❌ Mapeo {mapping_key} -> {mapping_value}: FALTANTE")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

def main():
    """Función principal de verificación"""
    print("🚀 Verificación simple de mejoras implementadas")
    print("=" * 60)
    
    tests = [
        ("Cambios en odoo-api", test_odoo_api_changes),
        ("Esquema de base de datos", test_database_schema_definition),
        ("Columnas en db_updater", test_db_updater_columns),
        ("Mapeo en sales_integration", test_sales_integration_mapping),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Error en {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Resumen de verificación:")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"   {status} - {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{len(results)} verificaciones pasaron")
    
    if passed == len(results):
        print("🎉 ¡Todas las mejoras están implementadas correctamente!")
        print("\n📝 Siguiente paso: Probar con datos reales cuando se resuelvan las dependencias")
        return 0
    else:
        print("⚠️  Algunas verificaciones fallaron. Revisar implementación.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 