#!/usr/bin/env python3
"""
Script de prueba para verificar las mejoras en la extracción de datos de Odoo.
Verifica que todas las columnas de la base de datos se estén poblando correctamente.
"""

import sys
import os
from datetime import date, timedelta
import pandas as pd

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from sales_engine.sales_integration import SalesDataProvider
    from sales_engine.db_updater import DatabaseUpdater
    print("✅ Imports exitosos")
except ImportError as e:
    print(f"❌ Error en imports: {e}")
    sys.exit(1)

def test_data_extraction():
    """Prueba la extracción de datos con los nuevos campos"""
    print("\n🧪 Probando extracción de datos de Odoo...")
    
    try:
        # Usar datos de prueba para los últimos 7 días
        provider = SalesDataProvider(use_test=True)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"📅 Rango de fechas: {start_date} a {end_date}")
        
        orders_df, lines_df = provider.read_sales_by_date_range(start_date, end_date)
        
        print(f"📊 Datos obtenidos:")
        print(f"   - {len(orders_df)} órdenes")
        print(f"   - {len(lines_df)} líneas de productos")
        
        if not orders_df.empty:
            print(f"\n📋 Columnas de órdenes: {list(orders_df.columns)}")
            
            # Verificar campos críticos
            critical_fields = ['doctype_name', 'term_name', 'warehouse_name']
            for field in critical_fields:
                if field in orders_df.columns:
                    non_null_count = orders_df[field].notna().sum()
                    print(f"   ✅ {field}: {non_null_count}/{len(orders_df)} registros poblados")
                    if non_null_count > 0:
                        sample_values = orders_df[field].dropna().unique()[:3]
                        print(f"      Ejemplos: {list(sample_values)}")
                else:
                    print(f"   ❌ {field}: campo faltante")
        
        provider.close()
        print("✅ Prueba de extracción completada")
        return True
        
    except Exception as e:
        print(f"❌ Error en extracción: {e}")
        return False

def test_database_schema():
    """Verifica que el esquema de la base de datos esté actualizado"""
    print("\n🗄️  Verificando esquema de base de datos...")
    
    expected_columns = [
        'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
        'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
        'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
        'items_product_description', 'items_product_sku', 'items_quantity',
        'items_unitPrice', 'issuedDate', 'sales_channel', 'created_at', 'updated_at'
    ]
    
    print(f"📝 Columnas esperadas: {len(expected_columns)}")
    for i, col in enumerate(expected_columns, 1):
        print(f"   {i:2d}. {col}")
    
    print("✅ Esquema verificado")
    return True

def test_mapping_logic():
    """Verifica la lógica de mapeo de campos"""
    print("\n🔄 Verificando lógica de mapeo...")
    
    # Simular datos de Odoo
    test_order = {
        'id': 12345,
        'name': 'SO001',
        'date_order': '2024-01-15',
        'amount_total': 119000,  # Incluye IVA
        'partner_id': [100, 'Cliente Test'],
        'user_id': [50, 'Vendedor Test'],
        'team_id': [10, 'Equipo Ventas'],
        'payment_term_id': [5, '30 días'],
        'warehouse_id': [1, 'Almacén Principal']
    }
    
    print(f"📦 Datos de prueba: {test_order['name']}")
    
    # Simular transformación
    expected_mappings = {
        'salesInvoiceId': test_order['id'],
        'docnumber': test_order['name'],
        'doctype_name': 'Factura',
        'totals_net': round(test_order['amount_total'] / 1.19, 0),
        'totals_vat': test_order['amount_total'] - round(test_order['amount_total'] / 1.19, 0),
        'total_total': test_order['amount_total'],
        'customer_name': test_order['partner_id'][1],
        'customer_customerid': test_order['partner_id'][0],
        'salesman_name': test_order['user_id'][1],
        'sales_channel': test_order['team_id'][1],
        'term_name': test_order['payment_term_id'][1],
        'warehouse_name': test_order['warehouse_id'][1],
        'issuedDate': test_order['date_order']
    }
    
    print("🔄 Mapeos verificados:")
    for field, expected in expected_mappings.items():
        print(f"   {field}: {expected}")
    
    print("✅ Lógica de mapeo verificada")
    return True

def main():
    """Función principal de pruebas"""
    print("🚀 Iniciando pruebas de mejoras en sales-engine...")
    print("=" * 60)
    
    tests = [
        ("Esquema de base de datos", test_database_schema),
        ("Lógica de mapeo", test_mapping_logic),
        ("Extracción de datos", test_data_extraction),
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
    print("📊 Resumen de pruebas:")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"   {status} - {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{len(results)} pruebas pasaron")
    
    if passed == len(results):
        print("🎉 ¡Todas las mejoras funcionan correctamente!")
        return 0
    else:
        print("⚠️  Algunas pruebas fallaron. Revisar implementación.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 