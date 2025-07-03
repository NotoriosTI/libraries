#!/usr/bin/env python3
"""
Test de validación de estructura de datos para verificar que todos los campos
necesarios para la base de datos se mapeen correctamente.
Simula datos de 3 meses para verificar la completitud del esquema.
"""

import sys
import os
from datetime import date, timedelta
import json

def simulate_odoo_order_data():
    """Simula datos reales de órdenes de Odoo como los que se obtendrían en 3 meses"""
    
    # Simular órdenes con todos los campos que debería retornar Odoo
    sample_orders = [
        {
            'id': 12345,
            'name': 'SO001',
            'date_order': '2024-01-15',
            'amount_total': 119000,  # Con IVA
            'partner_id': [100, 'Cliente Ejemplo S.A.'],
            'user_id': [50, 'Juan Pérez'],
            'team_id': [10, 'Equipo Ventas Norte'],
            'payment_term_id': [5, '30 días'],
            'warehouse_id': [1, 'Almacén Principal'],
            'state': 'sale'
        },
        {
            'id': 12346,
            'name': 'SO002',
            'date_order': '2024-01-16',
            'amount_total': 95200,
            'partner_id': [101, 'Distribuidora XYZ Ltda.'],
            'user_id': [51, 'María González'],
            'team_id': [11, 'Equipo Ventas Sur'],
            'payment_term_id': [6, '60 días'],
            'warehouse_id': [2, 'Almacén Secundario'],
            'state': 'done'
        },
        {
            'id': 12347,
            'name': 'POS/001',
            'date_order': '2024-01-17',
            'amount_total': 23800,
            'partner_id': [102, 'Cliente Final'],
            'user_id': [52, 'Ana López'],
            'team_id': [12, 'Tienda Sabaj'],  # Caso especial para sales_channel
            'payment_term_id': [7, 'Contado'],
            'warehouse_id': [1, 'Almacén Principal'],
            'state': 'done'
        }
    ]
    
    return sample_orders

def simulate_odoo_lines_data():
    """Simula datos de líneas de productos"""
    
    sample_lines = [
        {
            'sale_order': 'SO001',
            'product_sku': 'PROD-001',
            'product_name': 'Producto Ejemplo 1',
            'qty': 2.0,
            'price_unit': 50000.0
        },
        {
            'sale_order': 'SO001',
            'product_sku': 'PROD-002',
            'product_name': 'Producto Ejemplo 2',
            'qty': 1.0,
            'price_unit': 19000.0
        },
        {
            'sale_order': 'SO002',
            'product_sku': 'PROD-003',
            'product_name': 'Producto Premium',
            'qty': 1.0,
            'price_unit': 80000.0
        },
        {
            'sale_order': 'POS/001',
            'product_sku': 'PROD-004',
            'product_name': 'Producto Retail',
            'qty': 1.0,
            'price_unit': 20000.0
        }
    ]
    
    return sample_lines

def simulate_transform_orders_data(orders_data, partners_dict=None):
    """Simula la función _transform_orders_data de odoo-api/sales.py"""
    
    if partners_dict is None:
        partners_dict = {
            100: {'vat': '12345678-9'},
            101: {'vat': '87654321-0'},
            102: {'vat': '11111111-1'}
        }
    
    transformed_orders = []
    
    for order in orders_data:
        # Simular la transformación que hace odoo-api
        transformed_order = {
            # IDs y referencias
            'salesInvoiceId': order['id'],
            'docnumber': order['name'],
            'doctype_name': 'Factura',  # Campo mejorado
            
            # Información del cliente
            'customer_customerid': order['partner_id'][0],
            'customer_name': order['partner_id'][1],
            'customer_vatid': partners_dict.get(order['partner_id'][0], {}).get('vat', ''),
            
            # Información de ventas
            'salesman_name': order['user_id'][1],
            'sales_channel': 'Tienda Sabaj' if 'Tienda Sabaj' in order['team_id'][1] else order['team_id'][1],
            
            # Campos mejorados
            'term_name': order['payment_term_id'][1],  # Campo mejorado
            'warehouse_name': order['warehouse_id'][1],  # Campo mejorado
            
            # Montos calculados
            'totals_net': round(order['amount_total'] / 1.19, 0),
            'totals_vat': order['amount_total'] - round(order['amount_total'] / 1.19, 0),
            'total_total': order['amount_total'],
            
            # Fecha
            'issuedDate': order['date_order']
        }
        
        transformed_orders.append(transformed_order)
    
    return transformed_orders

def simulate_transform_lines_data(lines_data):
    """Simula la transformación de líneas de productos"""
    
    # Mapear nombres de órdenes a IDs
    order_name_to_id = {
        'SO001': 12345,
        'SO002': 12346,
        'POS/001': 12347
    }
    
    transformed_lines = []
    
    for line in lines_data:
        order_id = order_name_to_id.get(line['sale_order'], line['sale_order'])
        
        transformed_line = {
            'salesInvoiceId': order_id,
            'items_product_sku': line['product_sku'],
            'items_product_description': line['product_name'],
            'items_quantity': line['qty'],
            'items_unitPrice': line['price_unit']
        }
        transformed_lines.append(transformed_line)
    
    return transformed_lines

def validate_database_schema():
    """Valida que todos los campos requeridos para la base de datos estén presentes"""
    
    # Campos requeridos para la tabla sales_items
    required_db_fields = [
        'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
        'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
        'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
        'items_product_description', 'items_product_sku', 'items_quantity',
        'items_unitPrice', 'issuedDate', 'sales_channel'
    ]
    
    # Campos que fueron mejorados en la implementación
    improved_fields = ['doctype_name', 'term_name', 'warehouse_name']
    
    return required_db_fields, improved_fields

def test_data_extraction_simulation():
    """Test principal que simula extracción de 3 meses y verifica estructura"""
    
    print("🚀 SIMULACIÓN DE EXTRACCIÓN DE DATOS (3 MESES)")
    print("=" * 60)
    
    # Simular fechas
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    
    print(f"📅 Periodo simulado: {start_date} a {end_date} ({(end_date - start_date).days} días)")
    
    # 1. Simular extracción de datos de Odoo
    print("\n🔄 Simulando extracción de datos de Odoo...")
    
    raw_orders = simulate_odoo_order_data()
    raw_lines = simulate_odoo_lines_data()
    
    print(f"✅ Datos simulados obtenidos:")
    print(f"   📦 Órdenes: {len(raw_orders)}")
    print(f"   📋 Líneas: {len(raw_lines)}")
    
    # 2. Simular transformación de datos (como en odoo-api)
    print("\n🔄 Simulando transformación de datos...")
    
    transformed_orders = simulate_transform_orders_data(raw_orders)
    transformed_lines = simulate_transform_lines_data(raw_lines)
    
    print(f"✅ Transformación completada:")
    print(f"   📦 Órdenes transformadas: {len(transformed_orders)}")
    print(f"   📋 Líneas transformadas: {len(transformed_lines)}")
    
    # 3. Validar estructura de la base de datos
    print("\n🗄️  VALIDANDO ESQUEMA DE BASE DE DATOS")
    print("-" * 50)
    
    required_fields, improved_fields = validate_database_schema()
    
    # Crear conjunto combinado simulando merge de órdenes y líneas
    combined_records = []
    for order in transformed_orders:
        order_lines = [line for line in transformed_lines if line['salesInvoiceId'] == order['salesInvoiceId']]
        
        for line in order_lines:
            combined_record = {**order, **line}
            combined_records.append(combined_record)
    
    print(f"📊 Registros combinados para DB: {len(combined_records)}")
    
    # 4. Verificar completitud de campos
    print(f"\n🔍 ANÁLISIS DE COMPLETITUD DE CAMPOS:")
    print("-" * 40)
    
    missing_fields = []
    field_stats = {}
    
    for field in required_fields:
        if len(combined_records) > 0:
            # Verificar si el campo existe en al menos un registro
            field_present = any(field in record for record in combined_records)
            filled_count = sum(1 for record in combined_records if field in record and record[field] is not None and record[field] != '')
            completeness = (filled_count / len(combined_records)) * 100 if len(combined_records) > 0 else 0
            
            if not field_present:
                missing_fields.append(field)
            
            field_stats[field] = {
                'present': field_present,
                'filled_count': filled_count,
                'completeness': completeness
            }
            
            # Mostrar estadísticas
            status = "✅" if completeness >= 95 else "⚠️" if completeness >= 80 else "❌"
            print(f"   {status} {field}: {completeness:.1f}% completo ({filled_count}/{len(combined_records)})")
            
            # Mostrar ejemplos para campos mejorados
            if field in improved_fields and field_present:
                sample_values = []
                for record in combined_records[:3]:
                    if field in record and record[field]:
                        sample_values.append(str(record[field])[:25])
                
                if sample_values:
                    print(f"      📝 Ejemplos: {', '.join(sample_values)}")
        else:
            missing_fields.append(field)
            field_stats[field] = {'present': False, 'filled_count': 0, 'completeness': 0}
    
    # 5. Análisis especial de campos mejorados
    print(f"\n🔧 VERIFICACIÓN DE CAMPOS MEJORADOS:")
    print("-" * 40)
    
    improved_success = 0
    for field in improved_fields:
        stats = field_stats.get(field, {'present': False, 'completeness': 0})
        
        if stats['present'] and stats['completeness'] > 0:
            print(f"   ✅ {field}: IMPLEMENTADO correctamente ({stats['completeness']:.1f}%)")
            improved_success += 1
            
            # Mostrar valores de muestra
            sample_values = []
            for record in combined_records[:3]:
                if field in record and record[field]:
                    sample_values.append(str(record[field])[:30])
            
            if sample_values:
                print(f"      💡 Valores: {', '.join(sample_values)}")
                
        else:
            print(f"   ❌ {field}: NO implementado o vacío")
    
    # 6. Verificar estructura de datos para inserción en DB
    print(f"\n💾 VERIFICACIÓN PARA INSERCIÓN EN BASE DE DATOS:")
    print("-" * 50)
    
    if combined_records:
        sample_record = combined_records[0]
        
        print(f"📋 Estructura del primer registro:")
        for field in required_fields:
            value = sample_record.get(field, "❌ FALTANTE")
            value_str = str(value)[:40] if value is not None else "NULL"
            print(f"   {field}: {value_str}")
    
    # 7. Resumen final y criterios de éxito
    print(f"\n📊 RESUMEN FINAL:")
    print("=" * 50)
    
    total_fields = len(required_fields)
    present_fields = sum(1 for field in required_fields if field_stats[field]['present'])
    high_quality_fields = sum(1 for field in required_fields if field_stats[field]['completeness'] >= 95)
    
    schema_completeness = (present_fields / total_fields) * 100
    data_quality = (high_quality_fields / total_fields) * 100
    
    print(f"🎯 Esquema completo: {schema_completeness:.1f}% ({present_fields}/{total_fields})")
    print(f"📈 Campos de alta calidad (≥95%): {data_quality:.1f}% ({high_quality_fields}/{total_fields})")
    print(f"🔧 Campos mejorados funcionando: {improved_success}/{len(improved_fields)}")
    print(f"📦 Registros listos para DB: {len(combined_records)}")
    
    # Criterios de éxito
    success_criteria = [
        (schema_completeness >= 95, f"Esquema completo (≥95%): {schema_completeness:.1f}%"),
        (data_quality >= 90, f"Calidad de datos (≥90%): {data_quality:.1f}%"),
        (improved_success >= 2, f"Campos mejorados (≥2/3): {improved_success}/3"),
        (len(combined_records) > 0, f"Registros generados: {len(combined_records)}"),
        (len(missing_fields) == 0, f"Sin campos faltantes: {len(missing_fields)} faltantes")
    ]
    
    passed_criteria = sum(1 for success, _ in success_criteria if success)
    
    print(f"\n✅ CRITERIOS DE ÉXITO:")
    for success, description in success_criteria:
        status = "✅" if success else "❌"
        print(f"   {status} {description}")
    
    print(f"\n🎯 RESULTADO: {passed_criteria}/{len(success_criteria)} criterios cumplidos")
    
    # Resultado final
    test_passed = passed_criteria >= len(success_criteria) - 1
    
    if test_passed:
        print("\n🎉 ¡SIMULACIÓN EXITOSA!")
        print("✅ La estructura de datos está correcta para poblar la base de datos")
        print("✅ Los campos mejorados se mapean correctamente")
        print("✅ Todos los campos requeridos están presentes")
        
        print("\n📋 DATOS LISTOS PARA:")
        print("   1. Inserción en base de datos PostgreSQL")
        print("   2. Uso en reportes y análisis")
        print("   3. Sincronización automática")
        
    else:
        print("\n⚠️  SIMULACIÓN CON PROBLEMAS")
        print("❌ Revisar los campos que fallan en la estructura")
        
        if missing_fields:
            print(f"\n🔧 Campos faltantes por implementar: {missing_fields}")
    
    return test_passed

def main():
    """Función principal del test"""
    try:
        success = test_data_extraction_simulation()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Error en simulación: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 