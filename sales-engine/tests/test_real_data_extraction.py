#!/usr/bin/env python3
"""
Test de extracción real de datos de Odoo para los últimos 3 meses.
Verifica que todos los campos necesarios para la base de datos se obtengan correctamente.
"""

import sys
import os
from datetime import date, timedelta
import pandas as pd
from typing import Dict, List, Tuple

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from sales_engine.sales_integration import SalesDataProvider
    print("✅ Imports exitosos")
except ImportError as e:
    print(f"❌ Error en imports: {e}")
    sys.exit(1)

class DataQualityChecker:
    """Clase para verificar la calidad de los datos extraídos"""
    
    def __init__(self):
        # Campos obligatorios para la base de datos
        self.required_order_fields = [
            'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
            'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
            'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
            'issuedDate', 'sales_channel'
        ]
        
        self.required_line_fields = [
            'salesInvoiceId', 'items_product_description', 'items_product_sku',
            'items_quantity', 'items_unitPrice'
        ]
        
        # Campos que fueron mejorados en la implementación
        self.improved_fields = ['doctype_name', 'term_name', 'warehouse_name']
    
    def check_field_completeness(self, df: pd.DataFrame, field_name: str) -> Dict:
        """Verifica la completitud de un campo específico"""
        if df.empty:
            return {
                'field': field_name,
                'total_records': 0,
                'filled_records': 0,
                'completeness_rate': 0.0,
                'sample_values': []
            }
        
        total_records = len(df)
        filled_records = df[field_name].notna().sum() if field_name in df.columns else 0
        completeness_rate = (filled_records / total_records) * 100 if total_records > 0 else 0
        
        # Obtener valores de muestra (únicos, limitados a 5)
        sample_values = []
        if field_name in df.columns and filled_records > 0:
            sample_values = df[field_name].dropna().unique()[:5].tolist()
        
        return {
            'field': field_name,
            'total_records': total_records,
            'filled_records': filled_records,
            'completeness_rate': completeness_rate,
            'sample_values': sample_values
        }
    
    def analyze_data_quality(self, orders_df: pd.DataFrame, lines_df: pd.DataFrame) -> Dict:
        """Analiza la calidad completa de los datos extraídos"""
        results = {
            'orders': {
                'total_records': len(orders_df),
                'field_analysis': {},
                'missing_fields': []
            },
            'lines': {
                'total_records': len(lines_df),
                'field_analysis': {},
                'missing_fields': []
            },
            'improved_fields_analysis': {},
            'overall_quality': {}
        }
        
        # Analizar campos de órdenes
        for field in self.required_order_fields:
            if field not in orders_df.columns:
                results['orders']['missing_fields'].append(field)
            else:
                results['orders']['field_analysis'][field] = self.check_field_completeness(orders_df, field)
        
        # Analizar campos de líneas
        for field in self.required_line_fields:
            if field not in lines_df.columns:
                results['lines']['missing_fields'].append(field)
            else:
                results['lines']['field_analysis'][field] = self.check_field_completeness(lines_df, field)
        
        # Analizar campos mejorados específicamente
        for field in self.improved_fields:
            if field in orders_df.columns:
                results['improved_fields_analysis'][field] = self.check_field_completeness(orders_df, field)
        
        # Calcular calidad general
        total_required_fields = len(self.required_order_fields) + len(self.required_line_fields)
        total_present_fields = (len(self.required_order_fields) - len(results['orders']['missing_fields'])) + \
                              (len(self.required_line_fields) - len(results['lines']['missing_fields']))
        
        results['overall_quality'] = {
            'schema_completeness': (total_present_fields / total_required_fields) * 100,
            'total_records': len(orders_df) + len(lines_df),
            'orders_count': len(orders_df),
            'lines_count': len(lines_df)
        }
        
        return results

def test_three_months_data_extraction():
    """Test principal que extrae datos de los últimos 3 meses y verifica la calidad"""
    print("🚀 INICIANDO TEST DE EXTRACCIÓN DE DATOS (3 MESES)")
    print("=" * 70)
    
    # Configurar fechas (últimos 3 meses)
    end_date = date.today()
    start_date = end_date - timedelta(days=90)  # 3 meses aprox
    
    print(f"📅 Rango de extracción: {start_date} a {end_date}")
    print(f"📊 Periodo: {(end_date - start_date).days} días")
    
    # Inicializar proveedor de datos
    try:
        # Usar datos de producción (cambiar a use_test=True si prefieres datos de prueba)
        provider = SalesDataProvider(use_test=False)
        print("✅ Conexión a Odoo establecida")
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return False
    
    # Extraer datos
    try:
        print("\n🔄 Extrayendo datos de Odoo...")
        orders_df, lines_df = provider.read_sales_by_date_range(
            start_date=start_date,
            end_date=end_date,
            include_lines=True,
            batch_size=500
        )
        
        print(f"✅ Extracción completada:")
        print(f"   📦 Órdenes obtenidas: {len(orders_df)}")
        print(f"   📋 Líneas obtenidas: {len(lines_df)}")
        
    except Exception as e:
        print(f"❌ Error en extracción de datos: {e}")
        provider.close()
        return False
    
    # Verificar que obtuvimos datos
    if orders_df.empty:
        print("⚠️  No se obtuvieron órdenes en el periodo especificado")
        provider.close()
        return False
    
    # Analizar calidad de datos
    print(f"\n🔍 ANALIZANDO CALIDAD DE DATOS")
    print("-" * 50)
    
    checker = DataQualityChecker()
    quality_results = checker.analyze_data_quality(orders_df, lines_df)
    
    # Mostrar resultados de órdenes
    print(f"\n📦 ANÁLISIS DE ÓRDENES ({quality_results['orders']['total_records']} registros):")
    
    if quality_results['orders']['missing_fields']:
        print(f"❌ Campos faltantes: {quality_results['orders']['missing_fields']}")
    else:
        print("✅ Todos los campos requeridos están presentes")
    
    # Mostrar completitud por campo
    order_fields_ok = 0
    for field, analysis in quality_results['orders']['field_analysis'].items():
        completeness = analysis['completeness_rate']
        status = "✅" if completeness >= 95 else "⚠️" if completeness >= 80 else "❌"
        print(f"   {status} {field}: {completeness:.1f}% completo ({analysis['filled_records']}/{analysis['total_records']})")
        
        # Mostrar valores de muestra para campos mejorados
        if field in checker.improved_fields and analysis['sample_values']:
            sample_str = ", ".join(str(v)[:30] for v in analysis['sample_values'][:3])
            print(f"      📝 Ejemplos: {sample_str}")
        
        if completeness >= 95:
            order_fields_ok += 1
    
    # Mostrar resultados de líneas
    print(f"\n📋 ANÁLISIS DE LÍNEAS ({quality_results['lines']['total_records']} registros):")
    
    if quality_results['lines']['missing_fields']:
        print(f"❌ Campos faltantes: {quality_results['lines']['missing_fields']}")
    else:
        print("✅ Todos los campos requeridos están presentes")
    
    line_fields_ok = 0
    for field, analysis in quality_results['lines']['field_analysis'].items():
        completeness = analysis['completeness_rate']
        status = "✅" if completeness >= 95 else "⚠️" if completeness >= 80 else "❌"
        print(f"   {status} {field}: {completeness:.1f}% completo ({analysis['filled_records']}/{analysis['total_records']})")
        
        if completeness >= 95:
            line_fields_ok += 1
    
    # Análisis especial de campos mejorados
    print(f"\n🔧 ANÁLISIS DE CAMPOS MEJORADOS:")
    print("-" * 40)
    
    improved_success = 0
    for field, analysis in quality_results['improved_fields_analysis'].items():
        completeness = analysis['completeness_rate']
        status = "✅" if completeness > 0 else "❌"
        print(f"   {status} {field}: {completeness:.1f}% completo")
        
        if analysis['sample_values']:
            sample_str = ", ".join(str(v)[:25] for v in analysis['sample_values'][:3])
            print(f"      📝 Valores encontrados: {sample_str}")
            improved_success += 1
        else:
            print(f"      ⚠️  Sin valores encontrados")
    
    # Análisis de relaciones entre órdenes y líneas
    print(f"\n🔗 ANÁLISIS DE RELACIONES:")
    print("-" * 30)
    
    if not lines_df.empty and 'salesInvoiceId' in lines_df.columns:
        orders_with_lines = lines_df['salesInvoiceId'].nunique()
        total_orders = len(orders_df)
        coverage = (orders_with_lines / total_orders) * 100 if total_orders > 0 else 0
        
        print(f"   📊 Órdenes con líneas: {orders_with_lines}/{total_orders} ({coverage:.1f}%)")
        
        # Estadísticas de líneas por orden
        lines_per_order = lines_df.groupby('salesInvoiceId').size()
        print(f"   📈 Líneas por orden: promedio {lines_per_order.mean():.1f}, máximo {lines_per_order.max()}")
    
    # Resumen final
    print(f"\n📊 RESUMEN GENERAL:")
    print("=" * 50)
    
    schema_completeness = quality_results['overall_quality']['schema_completeness']
    total_required_fields = len(checker.required_order_fields) + len(checker.required_line_fields)
    fields_ok = order_fields_ok + line_fields_ok
    
    print(f"🎯 Esquema completo: {schema_completeness:.1f}%")
    print(f"📈 Campos con >95% completitud: {fields_ok}/{total_required_fields}")
    print(f"🔧 Campos mejorados funcionando: {improved_success}/{len(checker.improved_fields)}")
    print(f"📦 Total de registros procesados: {quality_results['overall_quality']['total_records']}")
    
    # Verificar criterios de éxito
    success_criteria = [
        (schema_completeness >= 95, f"Esquema completo (≥95%): {schema_completeness:.1f}%"),
        (fields_ok >= total_required_fields * 0.9, f"Campos completos (≥90%): {fields_ok}/{total_required_fields}"),
        (improved_success >= 2, f"Campos mejorados funcionando (≥2): {improved_success}/3"),
        (len(orders_df) > 0, f"Datos obtenidos: {len(orders_df)} órdenes"),
    ]
    
    passed_criteria = sum(1 for success, _ in success_criteria if success)
    
    print(f"\n✅ CRITERIOS DE ÉXITO:")
    for success, description in success_criteria:
        status = "✅" if success else "❌"
        print(f"   {status} {description}")
    
    print(f"\n🎯 RESULTADO FINAL: {passed_criteria}/{len(success_criteria)} criterios cumplidos")
    
    # Limpiar recursos
    provider.close()
    
    # Determinar si el test pasó
    test_passed = passed_criteria >= len(success_criteria) - 1  # Permitir 1 fallo
    
    if test_passed:
        print("\n🎉 ¡TEST EXITOSO! Los datos se extraen correctamente para poblar la base de datos")
        print("\n📋 PRÓXIMOS PASOS RECOMENDADOS:")
        print("   1. Ejecutar sincronización completa con estos datos")
        print("   2. Verificar la inserción en la base de datos")
        print("   3. Monitorear logs durante la próxima ejecución automática")
    else:
        print("\n⚠️  TEST CON PROBLEMAS. Revisar los campos que fallan.")
        print("     Posibles causas:")
        print("     - Configuración de conexión a Odoo")
        print("     - Permisos de acceso a datos")
        print("     - Mapeo de campos incompleto")
    
    return test_passed

def main():
    """Función principal del test"""
    try:
        success = test_three_months_data_extraction()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⏹️  Test interrumpido por el usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error inesperado en el test: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 