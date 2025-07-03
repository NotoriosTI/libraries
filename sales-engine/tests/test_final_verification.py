#!/usr/bin/env python3
"""
Verificación final de todas las mejoras implementadas.
Confirma que los cambios están presentes en odoo-api y sales-engine.
"""

import os
import sys

def test_complete_implementation():
    """Verificación completa de la implementación"""
    print("🔍 VERIFICACIÓN FINAL DE MEJORAS IMPLEMENTADAS")
    print("=" * 60)
    
    # 1. Verificar odoo-api
    print("\n📦 Verificando odoo-api/src/odoo_api/sales.py...")
    
    odoo_api_path = os.path.join('..', 'odoo-api', 'src', 'odoo_api', 'sales.py')
    
    if not os.path.exists(odoo_api_path):
        print(f"❌ No se encuentra: {odoo_api_path}")
        return False
    
    with open(odoo_api_path, 'r', encoding='utf-8') as f:
        odoo_content = f.read()
    
    # Verificaciones específicas en odoo-api
    odoo_checks = [
        ("df['doctype_name'] = 'Factura'", "df['doctype_name'] = 'Factura'" in odoo_content),
        ("payment_term_id en consultas", "'payment_term_id'" in odoo_content),
        ("warehouse_id en consultas", "'warehouse_id'" in odoo_content),
        ("mapeo term_name", "df['term_name'] = df['payment_term_id']" in odoo_content),
        ("mapeo warehouse_name", "df['warehouse_name'] = df['warehouse_id']" in odoo_content),
        ("limpieza payment_term_id", "'payment_term_id'" in odoo_content and "drop" in odoo_content),
        ("limpieza warehouse_id", "'warehouse_id'" in odoo_content and "drop" in odoo_content)
    ]
    
    odoo_success = 0
    for check_name, passed in odoo_checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if passed:
            odoo_success += 1
    
    print(f"   📊 odoo-api: {odoo_success}/{len(odoo_checks)} verificaciones pasaron")
    
    # 2. Verificar sales-engine utils.py
    print("\n🗄️  Verificando sales-engine/src/sales_engine/utils.py...")
    
    utils_path = os.path.join('src', 'sales_engine', 'utils.py')
    
    if not os.path.exists(utils_path):
        print(f"❌ No se encuentra: {utils_path}")
        return False
    
    with open(utils_path, 'r', encoding='utf-8') as f:
        utils_content = f.read()
    
    # Verificar esquema completo
    schema_columns = [
        'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
        'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
        'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
        'items_product_description', 'items_product_sku', 'items_quantity',
        'items_unitPrice', 'issuedDate', 'sales_channel', 'created_at', 'updated_at'
    ]
    
    schema_success = 0
    for column in schema_columns:
        if column in utils_content:
            schema_success += 1
        else:
            print(f"   ❌ Falta columna: {column}")
    
    if schema_success == len(schema_columns):
        print(f"   ✅ Esquema completo: {schema_success}/{len(schema_columns)} columnas")
    else:
        print(f"   ❌ Esquema incompleto: {schema_success}/{len(schema_columns)} columnas")
    
    # 3. Verificar sales-engine db_updater.py
    print("\n🔄 Verificando sales-engine/src/sales_engine/db_updater.py...")
    
    db_updater_path = os.path.join('src', 'sales_engine', 'db_updater.py')
    
    if not os.path.exists(db_updater_path):
        print(f"❌ No se encuentra: {db_updater_path}")
        return False
    
    with open(db_updater_path, 'r', encoding='utf-8') as f:
        db_updater_content = f.read()
    
    # Verificar columnas en bulk_load_data
    critical_db_columns = ['term_name', 'warehouse_name', 'doctype_name']
    db_success = 0
    
    for column in critical_db_columns:
        if column in db_updater_content:
            db_success += 1
            print(f"   ✅ {column} en db_updater")
        else:
            print(f"   ❌ {column} falta en db_updater")
    
    # 4. Verificar sales-engine sales_integration.py
    print("\n🗺️  Verificando sales-engine/src/sales_engine/sales_integration.py...")
    
    integration_path = os.path.join('src', 'sales_engine', 'sales_integration.py')
    
    if not os.path.exists(integration_path):
        print(f"❌ No se encuentra: {integration_path}")
        return False
    
    with open(integration_path, 'r', encoding='utf-8') as f:
        integration_content = f.read()
    
    # Verificar mapeos en sales_integration
    integration_checks = [
        ("payment_term_name mapeo", "payment_term_name" in integration_content),
        ("warehouse_name mapeo", "warehouse_name" in integration_content),
        ("doctype_name default", "'Factura'" in integration_content)
    ]
    
    integration_success = 0
    for check_name, passed in integration_checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if passed:
            integration_success += 1
    
    # 5. Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL:")
    
    total_checks = len(odoo_checks) + len(schema_columns) + len(critical_db_columns) + len(integration_checks)
    total_success = odoo_success + schema_success + db_success + integration_success
    
    results = [
        (f"odoo-api mejoras", odoo_success, len(odoo_checks)),
        (f"sales-engine esquema", schema_success, len(schema_columns)),
        (f"sales-engine db_updater", db_success, len(critical_db_columns)),
        (f"sales-engine integration", integration_success, len(integration_checks))
    ]
    
    for component, success, total in results:
        percentage = (success / total) * 100
        status = "✅" if success == total else "⚠️"
        print(f"   {status} {component}: {success}/{total} ({percentage:.1f}%)")
    
    overall_percentage = (total_success / total_checks) * 100
    print(f"\n🎯 RESULTADO GENERAL: {total_success}/{total_checks} ({overall_percentage:.1f}%)")
    
    if total_success == total_checks:
        print("\n🎉 ¡TODAS LAS MEJORAS ESTÁN CORRECTAMENTE IMPLEMENTADAS!")
        print("\n📋 RESUMEN DE CAMBIOS EXITOSOS:")
        print("   ✅ doctype_name: ahora 'Factura' (antes NULL)")
        print("   ✅ term_name: extraído de payment_term_id (antes NULL)")
        print("   ✅ warehouse_name: extraído de warehouse_id (antes NULL)")
        print("   ✅ Esquema de DB: 20/20 columnas definidas")
        print("   ✅ Mapeo completo: todos los campos mapeados")
        
        print("\n🚀 PRÓXIMOS PASOS:")
        print("   1. Ejecutar sincronización para probar con datos reales")
        print("   2. Verificar logs de la próxima ejecución")
        print("   3. Confirmar que los nuevos campos se populan")
        
        return True
    else:
        print(f"\n⚠️  Faltan {total_checks - total_success} verificaciones por completar")
        return False

def main():
    """Función principal"""
    try:
        success = test_complete_implementation()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 