"""
Test para verificar que el módulo production_forecast_reader funciona correctamente.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_import_production_forecast_reader():
    """Test para verificar que se puede importar el módulo."""
    try:
        from sales_engine.db_client.production_forecast_reader import (
            ProductionForecastReader, 
            get_production_forecasts_by_month
        )
        print("✅ Importación exitosa del módulo production_forecast_reader")
        return True
    except ImportError as e:
        print(f"❌ Error importando módulo: {e}")
        return False

def test_production_forecast_reader_functionality():
    """Test para verificar la funcionalidad básica."""
    try:
        from sales_engine.db_client.production_forecast_reader import ProductionForecastReader
        
        # Crear instancia
        reader = ProductionForecastReader()
        print("✅ Instancia de ProductionForecastReader creada exitosamente")
        
        # Obtener meses disponibles
        months = reader.get_available_months()
        print(f"✅ Meses disponibles obtenidos: {months}")
        
        # Si hay datos, probar obtener un mes específico
        if months:
            test_month = months[0]
            test_year = 2025  # Año actual
            
            # Obtener resumen
            summary = reader.get_production_forecast_summary(test_month, test_year)
            print(f"✅ Resumen obtenido para {test_month}/{test_year}: {summary['total_records']} registros")
            
            # Obtener datos completos
            df = reader.get_production_forecasts_by_month(test_month, test_year)
            print(f"✅ DataFrame obtenido: {len(df)} filas, {len(df.columns)} columnas")
            
            # Mostrar algunas columnas disponibles
            print(f"   Columnas disponibles: {list(df.columns)}")
            
            if not df.empty:
                print(f"   Top 3 por producción necesaria:")
                top_3 = df.nlargest(3, 'production_needed')[['sku', 'product_name', 'production_needed', 'priority']]
                for _, row in top_3.iterrows():
                    print(f"     {row['sku']}: {row['production_needed']:.2f} ({row['priority']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en funcionalidad: {e}")
        return False

def test_function_import():
    """Test para verificar la función de conveniencia."""
    try:
        from sales_engine.db_client.production_forecast_reader import get_production_forecasts_by_month
        
        # Probar con mes actual
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        df = get_production_forecasts_by_month(current_month, current_year)
        print(f"✅ Función de conveniencia funciona: {len(df)} registros para {current_month}/{current_year}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en función de conveniencia: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Production Forecast Reader Module")
    print("=" * 50)
    
    # Ejecutar tests
    tests = [
        ("Importación del módulo", test_import_production_forecast_reader),
        ("Funcionalidad básica", test_production_forecast_reader_functionality),
        ("Función de conveniencia", test_function_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Ejecutando: {test_name}")
        print("-" * 30)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASÓ")
        else:
            print(f"❌ {test_name}: FALLÓ")
    
    print(f"\n📊 Resumen: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron!")
        sys.exit(0)
    else:
        print("⚠️  Algunos tests fallaron")
        sys.exit(1) 