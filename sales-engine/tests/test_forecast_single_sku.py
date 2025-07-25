#!/usr/bin/env python3
"""
Test: Forecast para SKU específico usando SalesForecaster

Este test demuestra cómo generar forecast para un SKU específico
usando el SalesForecaster existente.
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Constante a nivel de módulo - SKU para el forecast
TARGET_SKU = "5958"

# Imports del sales engine
from sales_engine.forecaster.sales_forcaster import SalesForecaster
from sales_engine.db_client import DatabaseReader

def test_get_sku_historical_data(sku: str) -> pd.DataFrame:
    """Obtener datos históricos específicos para un SKU."""
    
    print(f"📊 Obteniendo datos históricos para SKU: {sku}")
    
    with DatabaseReader() as db:
        # Obtener datos de los últimos 3 años para tener suficiente historia
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)  # 3 años
        
        historical_data = db.get_sales_data(
            start_date=start_date,
            end_date=end_date,
            product_skus=[sku]
        )
        
        if historical_data.empty:
            print(f"   ❌ No se encontraron datos para SKU {sku}")
            return pd.DataFrame()
        
        print(f"   ✅ Encontrados {len(historical_data)} registros de ventas")
        print(f"   📅 Período: {historical_data['issueddate'].min()} a {historical_data['issueddate'].max()}")
        
        # Información resumida
        total_quantity = historical_data['items_quantity'].sum()
        total_revenue = historical_data['total_total'].sum()
        avg_price = historical_data['items_unitprice'].mean()
        
        print(f"   📦 Cantidad total vendida: {total_quantity:,.0f}")
        print(f"   💰 Ingresos totales: ${total_revenue:,.0f}")
        print(f"   💵 Precio promedio: ${avg_price:,.2f}")
        
        return historical_data


def test_single_sku_forecast(sku: str) -> pd.Series:
    """Generar forecast para un SKU específico usando SalesForecaster."""
    
    print(f"\n🔮 Generando forecast para SKU: {sku}")
    print("=" * 50)
    
    with SalesForecaster() as forecaster:
        # Obtener todos los datos históricos
        print("📥 Obteniendo datos históricos completos...")
        historical_data = forecaster.get_historical_sales_data()
        
        if historical_data is None:
            print("❌ No se pudieron obtener datos históricos")
            return pd.Series()
        
        # Filtrar solo el SKU objetivo
        sku_data = historical_data[historical_data['items_product_sku'] == sku].copy()
        
        if sku_data.empty:
            print(f"❌ No se encontraron datos para SKU {sku}")
            return pd.Series()
        
        print(f"✅ Datos encontrados para SKU {sku}: {len(sku_data)} registros")
        
        # Preparar series temporales mensuales
        print("📈 Preparando series temporales mensuales...")
        monthly_data = forecaster.prepare_monthly_time_series(sku_data)
        
        # Filtrar datos del SKU específico
        sku_monthly = monthly_data[monthly_data['sku'] == sku]
        
        if sku_monthly.empty:
            print(f"❌ No hay datos mensuales para SKU {sku}")
            return pd.Series()
        
        # Preparar la serie temporal
        ts_prepared = sku_monthly[['month', 'total_quantity']].set_index('month')['total_quantity']
        ts_prepared = ts_prepared.asfreq('ME', fill_value=0)
        ts_prepared.name = sku
        
        print(f"📊 Serie temporal preparada: {len(ts_prepared)} meses de datos")
        print(f"📅 Período: {ts_prepared.index.min()} a {ts_prepared.index.max()}")
        
        # Mostrar estadísticas de la serie
        print(f"📈 Estadísticas de ventas mensuales:")
        print(f"   📦 Promedio mensual: {ts_prepared.mean():.1f} unidades")
        print(f"   📊 Máximo mensual: {ts_prepared.max():.0f} unidades")
        print(f"   📉 Mínimo mensual: {ts_prepared.min():.0f} unidades")
        print(f"   📈 Desviación estándar: {ts_prepared.std():.1f}")
        
        # Generar forecast
        print(f"\n🎯 Generando forecast de 12 meses para SKU {sku}...")
        forecast_result = forecaster._forecast_single_sku(ts_prepared, steps=12)
        
        if forecast_result is None:
            print(f"❌ No se pudo generar forecast para SKU {sku}")
            return pd.Series()
        
        print(f"✅ Forecast generado exitosamente!")
        
        return forecast_result, ts_prepared


def test_display_forecast_results(sku: str, forecast: pd.Series, historical: pd.Series):
    """Mostrar resultados del forecast de manera detallada."""
    
    print(f"\n📋 Resultados del Forecast para SKU: {sku}")
    print("=" * 60)
    
    # Forecast mensual
    print("🔮 Forecast mensual (próximos 12 meses):")
    print("-" * 45)
    
    total_forecast = 0
    for i, (month, quantity) in enumerate(forecast.items(), 1):
        month_str = month.strftime('%Y-%m')
        total_forecast += quantity
        print(f"   {i:2}. {month_str} | {quantity:>6.0f} unidades")
    
    print("-" * 45)
    print(f"📦 Total forecast (12 meses): {total_forecast:,.0f} unidades")
    print(f"📊 Promedio mensual forecast: {total_forecast/12:,.1f} unidades")
    
    # Comparación con histórico
    if not historical.empty:
        print(f"\n📈 Comparación con datos históricos:")
        print("-" * 40)
        
        historical_avg = historical.mean()
        forecast_avg = forecast.mean()
        
        print(f"📊 Promedio mensual histórico: {historical_avg:.1f} unidades")
        print(f"🔮 Promedio mensual forecast: {forecast_avg:.1f} unidades")
        
        if forecast_avg > historical_avg:
            change = ((forecast_avg - historical_avg) / historical_avg) * 100
            print(f"📈 Tendencia: ↗️  Crecimiento del {change:.1f}%")
        elif forecast_avg < historical_avg:
            change = ((historical_avg - forecast_avg) / historical_avg) * 100
            print(f"📉 Tendencia: ↘️  Reducción del {change:.1f}%")
        else:
            print(f"➡️  Tendencia: Estable (sin cambios significativos)")
    
    # Resumen ejecutivo
    print(f"\n💼 Resumen Ejecutivo para SKU {sku}:")
    print("-" * 35)
    print(f"🎯 Forecast total (12 meses): {total_forecast:,.0f} unidades")
    print(f"📅 Período del forecast: {forecast.index[0].strftime('%Y-%m')} a {forecast.index[-1].strftime('%Y-%m')}")
    
    # Meses con mayor y menor demanda proyectada
    max_month = forecast.idxmax()
    min_month = forecast.idxmin()
    print(f"📈 Mes de mayor demanda: {max_month.strftime('%Y-%m')} ({forecast[max_month]:.0f} unidades)")
    print(f"📉 Mes de menor demanda: {min_month.strftime('%Y-%m')} ({forecast[min_month]:.0f} unidades)")


def test_save_forecast_results(sku: str, forecast: pd.Series):
    """Guardar resultados del forecast en archivo CSV."""
    
    try:
        # Crear DataFrame para exportar
        forecast_df = pd.DataFrame({
            'sku': sku,
            'month': forecast.index,
            'forecasted_quantity': forecast.values
        })
        
        # Agregar columnas adicionales útiles
        forecast_df['year'] = forecast_df['month'].dt.year
        forecast_df['month_name'] = forecast_df['month'].dt.strftime('%B')
        forecast_df['quarter'] = forecast_df['month'].dt.quarter
        
        # Guardar archivo
        filename = f"forecast_sku_{sku}_{date.today().strftime('%Y%m%d')}.csv"
        forecast_df.to_csv(filename, index=False)
        
        print(f"\n💾 Forecast guardado en: {filename}")
        print(f"📁 Columnas guardadas: {list(forecast_df.columns)}")
        
        return filename
        
    except Exception as e:
        print(f"\n❌ Error al guardar forecast: {str(e)}")
        return None


def main():
    """Función principal del test de forecast para SKU específico."""
    
    print("🧪 Test: Forecast para SKU específico")
    print("=" * 60)
    print(f"🎯 SKU objetivo: {TARGET_SKU}")
    print()
    
    try:
        # 1. Obtener datos históricos específicos del SKU
        historical_data = test_get_sku_historical_data(TARGET_SKU)
        
        if historical_data.empty:
            print(f"\n❌ No se pueden generar forecasts sin datos históricos para SKU {TARGET_SKU}")
            return 1
        
        # 2. Generar forecast usando SalesForecaster
        result = test_single_sku_forecast(TARGET_SKU)
        
        if isinstance(result, tuple) and len(result) == 2:
            forecast, historical_ts = result
        else:
            print(f"\n❌ No se pudo generar forecast para SKU {TARGET_SKU}")
            return 1
        
        # 3. Mostrar resultados detallados
        test_display_forecast_results(TARGET_SKU, forecast, historical_ts)
        
        # 4. Guardar resultados
        saved_file = test_save_forecast_results(TARGET_SKU, forecast)
        
        print(f"\n✅ Test completado exitosamente para SKU {TARGET_SKU}!")
        
        if saved_file:
            print(f"📁 Resultados guardados en: {saved_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error durante el test: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 