#!/usr/bin/env python3
"""
Test específico para funcionalidades del ForecastReader relacionadas con años

Este script prueba las capacidades del ForecastReader para:
- Obtener resúmenes de forecasts por año
- Listar meses disponibles por año
- Comparar datos entre diferentes años
- Validar la funcionalidad de filtrado por año
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Importar clases y funciones principales
from sales_engine.db_client.forecast_reader import ForecastReader, get_forecasts_by_month


def test_forecast_summary_by_year():
    """Probar la obtención de resúmenes de forecasts por año."""
    
    print("🧪 Probando resúmenes de forecasts por año")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        
        # 1. Resumen del año actual
        print(f"\n📊 Resumen del año {current_year}:")
        summary_current = reader.get_forecast_summary(current_year)
        
        if summary_current:
            print(f"   📦 SKUs únicos: {summary_current.get('unique_skus', 0):,}")
            print(f"   📊 Total registros: {summary_current.get('total_records', 0):,}")
            print(f"   📈 Total proyectado: {summary_current.get('total_forecasted_quantity', 0):,.1f}")
            print(f"   📅 Año: {summary_current.get('year', 'N/A')}")
        else:
            print(f"   ⚠️  No hay datos para el año {current_year}")
        
        # 2. Resumen general (todos los años)
        print(f"\n📊 Resumen general (todos los años):")
        summary_all = reader.get_forecast_summary()
        
        if summary_all:
            print(f"   📦 SKUs únicos: {summary_all.get('unique_skus', 0):,}")
            print(f"   📊 Total registros: {summary_all.get('total_records', 0):,}")
            print(f"   📈 Total proyectado: {summary_all.get('total_forecasted_quantity', 0):,.1f}")
            print(f"   📅 Año: {summary_all.get('year', 'N/A')}")
        else:
            print(f"   ⚠️  No hay datos disponibles")
        
        # 3. Probar años anteriores (si existen datos)
        previous_year = current_year - 1
        print(f"\n📊 Resumen del año {previous_year}:")
        summary_previous = reader.get_forecast_summary(previous_year)
        
        if summary_previous:
            print(f"   📦 SKUs únicos: {summary_previous.get('unique_skus', 0):,}")
            print(f"   📊 Total registros: {summary_previous.get('total_records', 0):,}")
            print(f"   📈 Total proyectado: {summary_previous.get('total_forecasted_quantity', 0):,.1f}")
        else:
            print(f"   ⚠️  No hay datos para el año {previous_year}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando resúmenes por año: {e}")
        return False


def test_available_months_by_year():
    """Probar la obtención de meses disponibles por año."""
    
    print("\n🧪 Probando meses disponibles por año")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        
        # 1. Meses disponibles para el año actual
        print(f"\n📅 Meses disponibles para {current_year}:")
        months_current = reader.get_available_months(current_year)
        
        if months_current:
            print(f"   📋 Meses: {sorted(months_current)}")
            print(f"   📊 Total meses: {len(months_current)}")
            
            # Mostrar algunos ejemplos de forecasts por mes
            for month in sorted(months_current)[:3]:  # Primeros 3 meses
                month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                month_name = month_names[month] if 1 <= month <= 12 else f"Mes_{month}"
                
                forecasts = reader.get_forecasts_by_month(month, current_year)
                print(f"   📈 {month_name}: {len(forecasts)} SKUs, {sum(forecasts.values()):.1f} unidades")
        else:
            print(f"   ⚠️  No hay datos para el año {current_year}")
        
        # 2. Todos los meses disponibles (sin filtro de año)
        print(f"\n📅 Todos los meses disponibles (sin filtro de año):")
        months_all = reader.get_available_months()
        
        if months_all:
            print(f"   📋 Meses: {sorted(months_all)}")
            print(f"   📊 Total meses: {len(months_all)}")
        else:
            print(f"   ⚠️  No hay datos disponibles")
        
        # 3. Probar año anterior
        previous_year = current_year - 1
        print(f"\n📅 Meses disponibles para {previous_year}:")
        months_previous = reader.get_available_months(previous_year)
        
        if months_previous:
            print(f"   📋 Meses: {sorted(months_previous)}")
            print(f"   📊 Total meses: {len(months_previous)}")
        else:
            print(f"   ⚠️  No hay datos para el año {previous_year}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando meses por año: {e}")
        return False


def test_forecast_comparison_by_year():
    """Probar comparaciones de forecasts entre diferentes años."""
    
    print("\n🧪 Probando comparaciones de forecasts entre años")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # 1. Comparar enero entre años
        print(f"\n📊 Comparando ENERO entre {previous_year} y {current_year}:")
        
        january_previous = reader.get_forecasts_by_month(1, previous_year)
        january_current = reader.get_forecasts_by_month(1, current_year)
        
        if january_previous and january_current:
            print(f"   📈 {previous_year}: {len(january_previous)} SKUs, {sum(january_previous.values()):.1f} unidades")
            print(f"   📈 {current_year}: {len(january_current)} SKUs, {sum(january_current.values()):.1f} unidades")
            
            # Calcular diferencia
            total_previous = sum(january_previous.values())
            total_current = sum(january_current.values())
            if total_previous > 0:
                change_percent = ((total_current - total_previous) / total_previous) * 100
                print(f"   📊 Cambio: {change_percent:+.1f}%")
        else:
            print(f"   ⚠️  No hay datos suficientes para comparar")
        
        # 2. Comparar diciembre entre años
        print(f"\n📊 Comparando DICIEMBRE entre {previous_year} y {current_year}:")
        
        december_previous = reader.get_forecasts_by_month(12, previous_year)
        december_current = reader.get_forecasts_by_month(12, current_year)
        
        if december_previous and december_current:
            print(f"   📈 {previous_year}: {len(december_previous)} SKUs, {sum(december_previous.values()):.1f} unidades")
            print(f"   📈 {current_year}: {len(december_current)} SKUs, {sum(december_current.values()):.1f} unidades")
            
            # Calcular diferencia
            total_previous = sum(december_previous.values())
            total_current = sum(december_current.values())
            if total_previous > 0:
                change_percent = ((total_current - total_previous) / total_previous) * 100
                print(f"   📊 Cambio: {change_percent:+.1f}%")
        else:
            print(f"   ⚠️  No hay datos suficientes para comparar")
        
        # 3. Top SKUs por año
        print(f"\n🏆 Top 5 SKUs por año:")
        
        for year in [previous_year, current_year]:
            print(f"\n   📅 {year}:")
            try:
                # Usar enero como referencia
                forecasts = reader.get_forecasts_by_month(1, year)
                if forecasts:
                    top_skus = sorted(forecasts.items(), key=lambda x: x[1], reverse=True)[:5]
                    for i, (sku, quantity) in enumerate(top_skus, 1):
                        print(f"      {i}. {sku}: {quantity:.1f} unidades")
                else:
                    print(f"      ⚠️  No hay datos para {year}")
            except Exception as e:
                print(f"      ❌ Error obteniendo top SKUs para {year}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando comparaciones por año: {e}")
        return False


def test_forecast_detailed_by_year():
    """Probar la obtención de forecasts detallados por año."""
    
    print("\n🧪 Probando forecasts detallados por año")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        
        # 1. Forecasts detallados para enero del año actual
        print(f"\n📊 Forecasts detallados para ENERO {current_year}:")
        january_detailed = reader.get_forecasts_by_month_detailed(1, current_year)
        
        if not january_detailed.empty:
            print(f"   📊 Total registros: {len(january_detailed)}")
            print(f"   📦 SKUs únicos: {january_detailed['sku'].nunique()}")
            print(f"   📈 Total proyectado: {january_detailed['forecasted_quantity'].sum():.1f}")
            
            # Mostrar columnas disponibles
            print(f"   📋 Columnas disponibles: {list(january_detailed.columns)}")
            
            # Mostrar algunos ejemplos
            print(f"\n   🔍 Primeros 3 registros:")
            for i, (_, row) in enumerate(january_detailed.head(3).iterrows()):
                print(f"      {i+1}. SKU: {row['sku']}, Cantidad: {row['forecasted_quantity']:.1f}")
        else:
            print(f"   ⚠️  No hay datos detallados para enero {current_year}")
        
        # 2. Forecasts detallados para diciembre del año actual
        print(f"\n📊 Forecasts detallados para DICIEMBRE {current_year}:")
        december_detailed = reader.get_forecasts_by_month_detailed(12, current_year)
        
        if not december_detailed.empty:
            print(f"   📊 Total registros: {len(december_detailed)}")
            print(f"   📦 SKUs únicos: {december_detailed['sku'].nunique()}")
            print(f"   📈 Total proyectado: {december_detailed['forecasted_quantity'].sum():.1f}")
        else:
            print(f"   ⚠️  No hay datos detallados para diciembre {current_year}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando forecasts detallados por año: {e}")
        return False


def test_sku_forecast_by_year():
    """Probar la obtención de forecasts para SKUs específicos por año."""
    
    print("\n🧪 Probando forecasts de SKUs específicos por año")
    print("=" * 60)
    
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        
        # SKUs de prueba (basados en datos comunes)
        test_skus = ['6912', '6889', '6911']
        
        for sku in test_skus:
            print(f"\n🔍 Forecast para SKU {sku} en {current_year}:")
            
            try:
                sku_forecast = reader.get_forecast_for_sku(sku, year=current_year)
                
                if sku_forecast:
                    print(f"   📊 Total quantity: {sku_forecast.get('total_quantity', 0):.1f}")
                    print(f"   📈 Avg monthly: {sku_forecast.get('avg_quantity', 0):.1f}")
                    print(f"   📅 Total forecasts: {sku_forecast.get('total_forecasts', 0)}")
                    print(f"   📋 Meses: {sku_forecast.get('months', [])}")
                else:
                    print(f"   ⚠️  No hay datos para SKU {sku} en {current_year}")
                    
            except Exception as e:
                print(f"   ❌ Error obteniendo forecast para SKU {sku}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando forecasts de SKUs por año: {e}")
        return False


def test_function_wrapper_by_year():
    """Probar la función wrapper get_forecasts_by_month con diferentes años."""
    
    print("\n🧪 Probando función wrapper con diferentes años")
    print("=" * 60)
    
    try:
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # 1. Función wrapper para año actual (por defecto)
        print(f"\n📊 Función wrapper para ENERO (año por defecto):")
        january_default = get_forecasts_by_month(1)
        print(f"   📦 Total SKUs: {len(january_default)}")
        print(f"   📈 Total unidades: {sum(january_default.values()):.1f}")
        
        # 2. Función wrapper para año específico
        print(f"\n📊 Función wrapper para ENERO {current_year} (año específico):")
        january_specific = get_forecasts_by_month(1, current_year)
        print(f"   📦 Total SKUs: {len(january_specific)}")
        print(f"   📈 Total unidades: {sum(january_specific.values()):.1f}")
        
        # 3. Función wrapper para año anterior
        print(f"\n📊 Función wrapper para ENERO {previous_year}:")
        january_previous = get_forecasts_by_month(1, previous_year)
        print(f"   📦 Total SKUs: {len(january_previous)}")
        print(f"   📈 Total unidades: {sum(january_previous.values()):.1f}")
        
        # 4. Comparar resultados
        if january_default and january_specific:
            print(f"\n📊 Comparación año por defecto vs año específico:")
            print(f"   📦 SKUs por defecto: {len(january_default)}")
            print(f"   📦 SKUs específico: {len(january_specific)}")
            print(f"   📈 Unidades por defecto: {sum(january_default.values()):.1f}")
            print(f"   📈 Unidades específico: {sum(january_specific.values()):.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando función wrapper por año: {e}")
        return False


def main():
    """Función principal que ejecuta todos los tests."""
    
    print("🧪 TEST FORECAST READER YEAR")
    print("=" * 60)
    print("Probando funcionalidades del ForecastReader relacionadas con años")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Lista de tests a ejecutar
    tests = [
        ("Resúmenes por año", test_forecast_summary_by_year),
        ("Meses disponibles por año", test_available_months_by_year),
        ("Comparaciones entre años", test_forecast_comparison_by_year),
        ("Forecasts detallados por año", test_forecast_detailed_by_year),
        ("Forecasts de SKUs por año", test_sku_forecast_by_year),
        ("Función wrapper por año", test_function_wrapper_by_year),
    ]
    
    # Ejecutar tests
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Error ejecutando {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen de resultados
    print(f"\n{'='*60}")
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"   {status} - {test_name}")
        if success:
            passed += 1
    
    print(f"\n📈 Resultado final: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron exitosamente!")
    else:
        print("⚠️  Algunos tests fallaron. Revisa los errores arriba.")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 