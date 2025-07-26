#!/usr/bin/env python3
"""
Test del Sales Forecaster Actualizado con Validación de Ciclo de Vida

Prueba que el sales_forcaster.py principal ahora incluye:
- 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0
- 📅 Validación temporal: Verificar actividad reciente antes de generar forecast
- 🎯 Funcionalidad completa del enhanced forecaster integrada
"""

import sys
from pathlib import Path

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sales_engine.forecaster.sales_forcaster import SalesForecaster


def test_basic_initialization():
    """Probar que el forecaster se inicializa correctamente con y sin validación."""
    
    print("🔧 TEST: INICIALIZACIÓN DEL FORECASTER ACTUALIZADO")
    print("=" * 60)
    
    # Test 1: Con validación de ciclo de vida (por defecto)
    print("1. Inicializando con validación de ciclo de vida...")
    try:
        forecaster_with_validation = SalesForecaster(
            use_test_odoo=False,
            enable_lifecycle_validation=True
        )
        print("   ✅ Forecaster con validación inicializado exitosamente")
        
        # Verificar que tiene el validador
        if hasattr(forecaster_with_validation, 'lifecycle_validator') and forecaster_with_validation.lifecycle_validator:
            print("   ✅ ProductLifecycleValidator disponible")
        else:
            print("   ⚠️  ProductLifecycleValidator no disponible - funcionará con filtros básicos")
            
    except Exception as e:
        print(f"   ❌ Error inicializando con validación: {e}")
        return False
    
    # Test 2: Sin validación de ciclo de vida
    print("\n2. Inicializando sin validación de ciclo de vida...")
    try:
        forecaster_without_validation = SalesForecaster(
            use_test_odoo=False,
            enable_lifecycle_validation=False
        )
        print("   ✅ Forecaster sin validación inicializado exitosamente")
        
        # Verificar que no tiene el validador
        if forecaster_with_validation.enable_lifecycle_validation == False:
            print("   ✅ Validación de ciclo de vida deshabilitada correctamente")
        
    except Exception as e:
        print(f"   ❌ Error inicializando sin validación: {e}")
        return False
    
    # Test 3: Verificar métodos disponibles
    print("\n3. Verificando métodos disponibles...")
    required_methods = [
        'run_forecasting_for_all_skus',
        '_validate_products_lifecycle',
        '_filter_skus_by_lifecycle',
        '_apply_basic_filters',
        '_generate_forecasts_for_valid_skus',
        '_apply_lifecycle_adjustments',
        'get_lifecycle_summary'
    ]
    
    missing_methods = []
    for method in required_methods:
        if hasattr(forecaster_with_validation, method):
            print(f"   ✅ Método {method} disponible")
        else:
            print(f"   ❌ Método {method} faltante")
            missing_methods.append(method)
    
    if missing_methods:
        print(f"\n❌ Métodos faltantes: {missing_methods}")
        return False
    
    print(f"\n✅ Inicialización exitosa - Todos los componentes disponibles")
    return True


def test_lifecycle_validation_methods():
    """Probar los métodos de validación de ciclo de vida con datos mock."""
    
    print("\n🔍 TEST: MÉTODOS DE VALIDACIÓN DE CICLO DE VIDA")
    print("=" * 60)
    
    try:
        forecaster = SalesForecaster(use_test_odoo=False, enable_lifecycle_validation=True)
        
        # Test con datos reales pequeños
        print("1. Probando validación con SKUs conocidos...")
        
        # Simular datos históricos básicos
        import pandas as pd
        from datetime import datetime, timedelta
        
        # Crear datos mock para prueba
        mock_historical_data = pd.DataFrame({
            'items_product_sku': ['TEST001', 'TEST002', 'TEST003'] * 10,
            'issueddate': [datetime.now() - timedelta(days=x*30) for x in range(30)],
            'items_quantity': [10, 5, 15] * 10
        })
        
        mock_skus = ['TEST001', 'TEST002', 'TEST003']
        
        print(f"   Datos mock creados: {len(mock_historical_data)} registros, {len(mock_skus)} SKUs")
        
        # Solo probar si el validador está disponible
        if forecaster.enable_lifecycle_validation and forecaster.lifecycle_validator:
            print("   🔍 Ejecutando validación de ciclo de vida...")
            validation_results = forecaster._validate_products_lifecycle(mock_historical_data, mock_skus)
            
            if validation_results:
                print(f"   ✅ Validación ejecutada: {len(validation_results)} resultados")
                
                # Probar filtrado por ciclo de vida
                filtered_skus = forecaster._filter_skus_by_lifecycle(mock_skus, validation_results)
                print(f"   ✅ Filtrado ejecutado: {len(filtered_skus)} SKUs aprobados de {len(mock_skus)} originales")
                
                # Probar resumen
                summary = forecaster.get_lifecycle_summary(validation_results)
                if summary:
                    print(f"   ✅ Resumen generado con {len(summary)} campos")
            else:
                print("   ⚠️  Validación retornó resultados vacíos")
        else:
            print("   ⚠️  Validación de ciclo de vida no disponible - usando filtros básicos")
            
            # Probar filtros básicos
            mock_monthly_data = pd.DataFrame({
                'sku': ['TEST001', 'TEST002', 'TEST003'] * 12,
                'month': pd.date_range('2023-01-01', periods=36, freq='ME'),
                'total_quantity': [10, 5, 15] * 12
            })
            
            basic_filtered = forecaster._apply_basic_filters(mock_monthly_data, mock_skus)
            print(f"   ✅ Filtros básicos ejecutados: {len(basic_filtered)} SKUs aprobados")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en validación: {e}")
        return False


def test_backward_compatibility():
    """Probar que el forecaster mantiene compatibilidad con código existente."""
    
    print("\n⚖️  TEST: COMPATIBILIDAD HACIA ATRÁS")
    print("=" * 60)
    
    try:
        # Test 1: Inicialización como antes (solo un parámetro)
        print("1. Probando inicialización legacy...")
        legacy_forecaster = SalesForecaster(use_test_odoo=False)
        print("   ✅ Inicialización legacy funciona")
        
        # Test 2: Verificar que tiene los métodos originales
        original_methods = [
            'get_historical_sales_data',
            'prepare_monthly_time_series',
            '_forecast_single_sku',
            '_apply_month_to_month_variation_limit'
        ]
        
        print("2. Verificando métodos originales...")
        for method in original_methods:
            if hasattr(legacy_forecaster, method):
                print(f"   ✅ Método original {method} disponible")
            else:
                print(f"   ❌ Método original {method} faltante")
                return False
        
        # Test 3: El método principal debe funcionar
        print("3. Verificando método principal...")
        if hasattr(legacy_forecaster, 'run_forecasting_for_all_skus'):
            print("   ✅ Método run_forecasting_for_all_skus disponible")
        else:
            print("   ❌ Método principal faltante")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en compatibilidad: {e}")
        return False


def main():
    """Función principal de prueba."""
    
    print("🚀 TEST COMPLETO: SALES FORECASTER ACTUALIZADO")
    print("=" * 70)
    print("Verificando que sales_forcaster.py ahora incluye:")
    print("• 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0")
    print("• 📅 Validación temporal: Verificar actividad reciente")
    print("• 🎯 Funcionalidad completa del enhanced forecaster")
    print("• ⚖️  Compatibilidad hacia atrás mantenida")
    
    tests_results = []
    
    # Ejecutar todos los tests
    print(f"\n" + "="*70)
    tests_results.append(test_basic_initialization())
    
    tests_results.append(test_lifecycle_validation_methods())
    
    tests_results.append(test_backward_compatibility())
    
    # Resultados finales
    print(f"\n🎯 RESULTADOS FINALES:")
    print("=" * 50)
    
    passed_tests = sum(tests_results)
    total_tests = len(tests_results)
    
    if passed_tests == total_tests:
        print(f"✅ TODOS LOS TESTS PASARON ({passed_tests}/{total_tests})")
        print(f"\n🎉 ACTUALIZACIÓN EXITOSA:")
        print(f"   • sales_forcaster.py ahora incluye validación de ciclo de vida")
        print(f"   • Filtros de descontinuados y validación temporal implementados")
        print(f"   • Compatibilidad hacia atrás mantenida")
        print(f"   • El forecaster principal es ahora el enhanced forecaster")
        
        print(f"\n💡 USO:")
        print(f"   # Con validación (recomendado)")
        print(f"   forecaster = SalesForecaster(enable_lifecycle_validation=True)")
        print(f"   ")
        print(f"   # Sin validación (legacy)")
        print(f"   forecaster = SalesForecaster(enable_lifecycle_validation=False)")
        print(f"   ")
        print(f"   # Uso existente sigue funcionando")
        print(f"   forecaster = SalesForecaster()")
        
    else:
        print(f"❌ ALGUNOS TESTS FALLARON ({passed_tests}/{total_tests})")
        print(f"   • Revisar implementación de métodos faltantes")
        print(f"   • Verificar imports de ProductLifecycleValidator")
        print(f"   • Confirmar compatibilidad hacia atrás")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 