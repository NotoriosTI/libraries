#!/usr/bin/env python3
"""
Script de ejemplo para probar ForecastReader

Demuestra cómo usar la función get_forecasts_by_month que toma
un mes como argumento y retorna un diccionario con SKUs y predicciones.
"""

import sys
from pathlib import Path

# Agregar src al path para imports (desde tests/ hacia src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Importar función principal
from sales_engine.db_client.forecast_reader import get_forecasts_by_month, ForecastReader


def test_get_forecasts_by_month():
    """Probar la función principal que pidió el usuario."""
    
    print("🧪 Probando función get_forecasts_by_month()")
    print("=" * 60)
    
    # Probar la función de conveniencia directa
    try:
        # Ejemplo 1: Enero
        print("\n📅 Obteniendo forecasts para ENERO (mes 1):")
        january_forecasts = get_forecasts_by_month(1)
        
        print(f"   📦 Total SKUs: {len(january_forecasts)}")
        print(f"   📊 Total unidades: {sum(january_forecasts.values()):.1f}")
        
        # Mostrar algunos ejemplos
        print(f"\n   🔍 Primeros 5 SKUs:")
        for i, (sku, quantity) in enumerate(list(january_forecasts.items())[:5]):
            print(f"      {sku}: {quantity:.1f} unidades")
        
        # Ejemplo 2: Diciembre (pico de demanda)
        print("\n📅 Obteniendo forecasts para DICIEMBRE (mes 12):")
        december_forecasts = get_forecasts_by_month(12)
        
        print(f"   📦 Total SKUs: {len(december_forecasts)}")
        print(f"   📊 Total unidades: {sum(december_forecasts.values()):.1f}")
        
        # Top 5 productos en diciembre
        sorted_dec = sorted(december_forecasts.items(), key=lambda x: x[1], reverse=True)
        print(f"\n   🏆 Top 5 SKUs en diciembre:")
        for i, (sku, quantity) in enumerate(sorted_dec[:5]):
            print(f"      {i+1}. {sku}: {quantity:.1f} unidades")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando función: {e}")
        return False


def test_forecast_reader_class():
    """Probar la clase ForecastReader con funciones adicionales."""
    
    print("\n🧪 Probando clase ForecastReader")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        
        # 1. Resumen general
        print("\n📊 Resumen general:")
        summary = reader.get_forecast_summary()
        print(f"   📦 SKUs únicos: {summary['unique_skus']:,}")
        print(f"   📊 Total registros: {summary['total_records']:,}")
        print(f"   📈 Total proyectado: {summary['total_forecasted_quantity']:,.1f}")
        
        # 2. Meses disponibles
        months = reader.get_available_months()
        print(f"\n📅 Meses disponibles: {months}")
        
        # 3. Forecast para un SKU específico
        print(f"\n🔍 Forecast detallado para SKU '6912' (top producto):")
        sku_forecast = reader.get_forecast_for_sku('6912')
        if sku_forecast:
            print(f"   📊 Total quantity: {sku_forecast['total_quantity']:.1f}")
            print(f"   📈 Avg monthly: {sku_forecast['avg_quantity']:.1f}")
            print(f"   📅 Forecasts: {sku_forecast['total_forecasts']}")
        
        # 4. Forecasts detallados de un mes
        print(f"\n📈 Forecasts detallados para marzo (muestra):")
        march_detailed = reader.get_forecasts_by_month_detailed(3)
        if not march_detailed.empty:
            print(f"   📊 Registros: {len(march_detailed)}")
            print(f"   📦 SKUs únicos: {march_detailed['sku'].nunique()}")
            
            # Mostrar algunos ejemplos
            top_march = march_detailed.nlargest(3, 'forecasted_quantity')
            print(f"   🏆 Top 3 en marzo:")
            for _, row in top_march.iterrows():
                print(f"      {row['sku']}: {row['forecasted_quantity']} unidades ({row['month_name']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando clase: {e}")
        return False


def demonstrate_usage():
    """Demostrar casos de uso prácticos."""
    
    print("\n💡 Casos de Uso Prácticos")
    print("=" * 60)
    
    try:
        # Caso 1: Comparar demanda estacional
        print("\n📊 Comparación de demanda estacional:")
        
        seasons = {
            "Invierno (Enero)": 1,
            "Primavera (Abril)": 4, 
            "Verano (Julio)": 7,
            "Otoño (Octubre)": 10
        }
        
        for season_name, month in seasons.items():
            forecasts = get_forecasts_by_month(month)
            total = sum(forecasts.values())
            print(f"   {season_name:20}: {total:8.1f} unidades ({len(forecasts)} SKUs)")
        
        # Caso 2: Encontrar productos con alta demanda en un mes específico
        print(f"\n🔥 Productos con alta demanda en Diciembre:")
        december_forecasts = get_forecasts_by_month(12)
        high_demand = {sku: qty for sku, qty in december_forecasts.items() if qty > 100}
        
        print(f"   📦 SKUs con >100 unidades: {len(high_demand)}")
        
        # Top 3 alta demanda
        sorted_high = sorted(high_demand.items(), key=lambda x: x[1], reverse=True)[:3]
        for i, (sku, qty) in enumerate(sorted_high):
            print(f"   {i+1}. {sku}: {qty:.1f} unidades")
        
        # Caso 3: Validar entrada de función
        print(f"\n⚠️  Validación de entrada:")
        try:
            get_forecasts_by_month(13)  # Mes inválido
        except ValueError as e:
            print(f"   ✅ Error capturado correctamente: {e}")
        
        try:
            get_forecasts_by_month("enero")  # Tipo inválido
        except ValueError as e:
            print(f"   ✅ Error capturado correctamente: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en casos de uso: {e}")
        return False


def test_simple_usage():
    """Test simple para demostrar el uso básico de la función principal."""
    
    print("\n🎯 Test Simple - Uso Básico")
    print("=" * 60)
    
    try:
        # Obtener forecasts para enero
        january_forecasts = get_forecasts_by_month(1)
        
        # Verificar que tenemos el SKU 6518
        if '6518' in january_forecasts:
            product_6518 = january_forecasts['6518']
            print(f"✅ Forecast para SKU 6518 en enero: {product_6518} unidades")
        else:
            print("❌ SKU 6518 no encontrado en forecasts de enero")
            return False
        
        print(f"📊 Total SKUs en enero: {len(january_forecasts)}")
        print(f"📈 Total unidades proyectadas: {sum(january_forecasts.values()):.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en test simple: {e}")
        return False


def main():
    """Función principal para ejecutar todas las pruebas."""
    
    print("🎯 Test Script para ForecastReader")
    print("=" * 70)
    print("Este script demuestra cómo usar la función get_forecasts_by_month(month: int)")
    print("que retorna un Dict[str, float] con SKUs y predicciones para el mes dado.")
    print("=" * 70)
    
    tests = [
        ("Función Principal", test_get_forecasts_by_month),
        ("Clase Completa", test_forecast_reader_class),
        ("Casos de Uso", demonstrate_usage),
        ("Uso Simple", test_simple_usage)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
    
    print(f"\n{'='*70}")
    print(f"📊 Resumen: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        print("\n💡 Uso básico de la función:")
        print("   from sales_engine.db_client import get_forecasts_by_month")
        print("   forecasts = get_forecasts_by_month(1)  # Enero")
        print("   print(f'Total SKUs: {len(forecasts)}')")
        print("   print(f'Total unidades: {sum(forecasts.values())}')")
        return 0
    else:
        print("⚠️  Algunos tests fallaron")
        return 1


if __name__ == "__main__":
    print("🔍 DEBUG: Ejecutando main...")
    sys.exit(main()) 