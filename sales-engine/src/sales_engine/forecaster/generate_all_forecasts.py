#!/usr/bin/env python3
"""
Generador de Forecasts para Todos los Productos (con Limpieza Integrada)

Este script genera proyecciones SARIMA para todos los SKUs, 
limpia valores extremos y exporta tanto versiones originales 
como limpias para análisis posterior.
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Crear directorio de forecasts si no existe
FORECASTS_DIR = Path("data/forecasts")
FORECASTS_DIR.mkdir(parents=True, exist_ok=True)

# Imports
from sales_engine.forecaster import SalesForecaster

# Si se usa PrettyLogger, importar correctamente
# from dev_utils import PrettyLogger

def generate_all_forecasts():
    """Generar forecasts para todos los productos."""
    
    print("🚀 Generando Forecasts para Todos los Productos")
    print("=" * 60)
    
    try:
        forecaster = SalesForecaster()
        print("📊 Iniciando proceso de forecasting para todos los SKUs...")
        # Generar forecasts para todos los productos
        all_forecasts = forecaster.run_forecasting_for_all_skus()
        if not all_forecasts:
            print("❌ No se generaron forecasts")
            return None
        print(f"✅ Forecasts generados para {len(all_forecasts)} productos")
        return all_forecasts
            
    except Exception as e:
        print(f"❌ Error generando forecasts: {str(e)}")
        return None

def convert_to_dataframe(forecasts_dict):
    """Convertir diccionario de forecasts a DataFrame estructurado."""
    
    print("\n🔄 Convirtiendo forecasts a DataFrame...")
    
    # Lista para almacenar todas las filas
    forecast_rows = []
    
    for sku, forecast_series in forecasts_dict.items():
        print(f"   📦 Procesando SKU: {sku}")
        
        for date, quantity in forecast_series.items():
            forecast_rows.append({
                'sku': sku,
                'forecast_date': date,
                'forecasted_quantity': int(quantity),
                'year': date.year,
                'month': date.month,
                'month_name': date.strftime('%B'),
                'quarter': f"Q{((date.month-1)//3)+1}",
                'week_of_year': date.isocalendar()[1]
            })
    
    # Crear DataFrame
    df = pd.DataFrame(forecast_rows)
    
    # Ordenar por SKU y fecha
    df = df.sort_values(['sku', 'forecast_date']).reset_index(drop=True)
    
    print(f"✅ DataFrame creado con {len(df)} registros")
    print(f"   📦 SKUs únicos: {df['sku'].nunique()}")
    print(f"   📅 Período: {df['forecast_date'].min()} a {df['forecast_date'].max()}")
    
    return df

def add_summary_statistics(df):
    """Agregar estadísticas de resumen por SKU."""
    
    print("\n📊 Calculando estadísticas de resumen...")
    
    # Estadísticas por SKU
    sku_stats = df.groupby('sku')['forecasted_quantity'].agg([
        'sum', 'mean', 'std', 'min', 'max', 'count'
    ]).round(2)
    
    sku_stats.columns = [
        'total_forecast_12_months',
        'avg_monthly_forecast', 
        'std_dev',
        'min_monthly_forecast',
        'max_monthly_forecast',
        'months_forecasted'
    ]
    
    # Resetear índice para tener SKU como columna
    sku_stats = sku_stats.reset_index()
    
    # Agregar estadísticas al DataFrame principal
    df_with_stats = df.merge(sku_stats, on='sku', how='left')
    
    print(f"✅ Estadísticas agregadas para {len(sku_stats)} SKUs")
    
    return df_with_stats, sku_stats

def export_to_csv(df, sku_stats):
    """Exportar DataFrames a archivos CSV (versión original)."""
    
    print("\n💾 Exportando archivos originales...")
    
    # Fecha para el nombre del archivo
    today = date.today().strftime('%Y%m%d')
    
    # 1. Archivo principal con todos los forecasts
    main_filename = f"forecasts_all_products_{today}.csv"
    main_filepath = FORECASTS_DIR / main_filename
    df.to_csv(main_filepath, index=False)
    print(f"📁 Forecast detallado guardado: {main_filepath}")
    print(f"   📊 Registros: {len(df):,}")
    print(f"   📋 Columnas: {list(df.columns)}")
    
    # 2. Archivo de resumen por SKU
    summary_filename = f"forecast_summary_by_sku_{today}.csv"
    summary_filepath = FORECASTS_DIR / summary_filename
    sku_stats.to_csv(summary_filepath, index=False)
    print(f"📁 Resumen por SKU guardado: {summary_filepath}")
    print(f"   📊 SKUs: {len(sku_stats):,}")
    print(f"   📋 Columnas: {list(sku_stats.columns)}")
    
    # 3. Archivo pivoteado (SKUs como columnas, fechas como filas)
    pivot_df = df.pivot(index='forecast_date', columns='sku', values='forecasted_quantity')
    pivot_filename = f"forecasts_pivot_table_{today}.csv"
    pivot_filepath = FORECASTS_DIR / pivot_filename
    pivot_df.to_csv(pivot_filepath)
    print(f"📁 Tabla pivoteada guardada: {pivot_filepath}")
    print(f"   📅 Fechas: {len(pivot_df)}")
    print(f"   📦 SKUs: {len(pivot_df.columns)}")
    
    return {
        'main_file': str(main_filepath),
        'summary_file': str(summary_filepath),
        'pivot_file': str(pivot_filepath)
    }

def show_top_products(sku_stats, top_n=10):
    """Mostrar los productos con mayores proyecciones."""
    
    print(f"\n🏆 Top {top_n} Productos por Forecast Total (12 meses)")
    print("=" * 60)
    
    top_products = sku_stats.nlargest(top_n, 'total_forecast_12_months')
    
    print(" Rank | SKU      | Total 12M | Prom/Mes | Min  | Max  | Desv.Std")
    print("-" * 65)
    
    for i, (_, row) in enumerate(top_products.iterrows(), 1):
        print(f" {i:4} | {row['sku']:8} | {row['total_forecast_12_months']:9,.0f} | {row['avg_monthly_forecast']:8.1f} | {row['min_monthly_forecast']:4.0f} | {row['max_monthly_forecast']:4.0f} | {row['std_dev']:8.1f}")

def show_forecast_overview(df):
    """Mostrar resumen general de todos los forecasts."""
    
    print(f"\n📈 Resumen General de Forecasts")
    print("=" * 40)
    
    # Estadísticas generales
    total_products = df['sku'].nunique()
    total_forecast = df['forecasted_quantity'].sum()
    avg_monthly = df['forecasted_quantity'].mean()
    
    print(f"📦 Total productos con forecast: {total_products:,}")
    print(f"📊 Total proyectado (12 meses): {total_forecast:,} unidades")
    print(f"📈 Promedio mensual general: {avg_monthly:.1f} unidades")
    
    # Por mes
    monthly_totals = df.groupby('month_name')['forecasted_quantity'].sum()
    max_month = monthly_totals.idxmax()
    min_month = monthly_totals.idxmin()
    
    print(f"\n📅 Estacionalidad General:")
    print(f"   🔥 Mes con mayor demanda: {max_month} ({monthly_totals[max_month]:,} unidades)")
    print(f"   ❄️  Mes con menor demanda: {min_month} ({monthly_totals[min_month]:,} unidades)")
    
    # Por trimestre
    quarterly_totals = df.groupby('quarter')['forecasted_quantity'].sum()
    print(f"\n📊 Por Trimestre:")
    for quarter, total in quarterly_totals.items():
        print(f"   {quarter}: {total:,} unidades")

def show_quality_analysis(df, summary_df):
    """Mostrar análisis de calidad de los forecasts sin modificar datos."""
    
    print("\n📊 Análisis de Calidad de Forecasts")
    print("=" * 50)
    
    # Estadísticas descriptivas generales (solo informativo)
    quantities = df['forecasted_quantity']
    
    print(f"📈 Distribución Global de Forecasts:")
    print(f"   Total registros: {len(df):,}")
    print(f"   Mínimo: {quantities.min()}")
    print(f"   Q25: {quantities.quantile(0.25):,.0f}")
    print(f"   Mediana: {quantities.median():,.0f}")
    print(f"   Q75: {quantities.quantile(0.75):,.0f}")
    print(f"   Q90: {quantities.quantile(0.90):,.0f}")
    print(f"   Q99: {quantities.quantile(0.99):,.0f}")
    print(f"   Máximo: {quantities.max():,}")
    print(f"   Media: {quantities.mean():.1f}")
    print(f"   Desv. Estándar: {quantities.std():.1f}")
    
    # Análisis por categorías de rotación
    print(f"\n🏷️ Análisis por Categorías de Rotación:")
    
    # Categorizar SKUs por volumen total proyectado
    high_volume = summary_df[summary_df['total_forecast_12_months'] >= 1000]
    medium_volume = summary_df[(summary_df['total_forecast_12_months'] >= 100) & 
                              (summary_df['total_forecast_12_months'] < 1000)]
    low_volume = summary_df[summary_df['total_forecast_12_months'] < 100]
    
    print(f"   🔥 Alta rotación (≥1000/año): {len(high_volume)} SKUs")
    if len(high_volume) > 0:
        print(f"      Promedio mensual: {high_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {high_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {high_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    print(f"   📊 Media rotación (100-999/año): {len(medium_volume)} SKUs")
    if len(medium_volume) > 0:
        print(f"      Promedio mensual: {medium_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {medium_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {medium_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    print(f"   📉 Baja rotación (<100/año): {len(low_volume)} SKUs")
    if len(low_volume) > 0:
        print(f"      Promedio mensual: {low_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {low_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {low_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    # Verificar consistencia
    print(f"\n✅ Verificación de Consistencia:")
    inconsistent = summary_df[summary_df['max_monthly_forecast'] < summary_df['avg_monthly_forecast']]
    print(f"   📊 SKUs con max < promedio: {len(inconsistent)}")
    
    negative_skus = summary_df[summary_df['min_monthly_forecast'] < 0]
    print(f"   🔴 SKUs con valores negativos: {len(negative_skus)}")
    
    if len(inconsistent) == 0 and len(negative_skus) == 0:
        print(f"   ✅ Todos los forecasts son consistentes y válidos")
    
    print(f"\n💡 Interpretación:")
    print(f"   🎯 Los forecasts se generaron con validación individual por SKU")
    print(f"   📊 Cada producto tiene límites basados en su historial específico")
    print(f"   ✅ No se aplicó limpieza global que podría distorsionar patrones naturales")



def main():
    """Función principal con limpieza integrada."""
    
    print("🎯 Generador de Forecasts - Todos los Productos (con Limpieza)")
    print("=" * 70)
    print(f"📁 Los archivos CSV se guardarán en: {FORECASTS_DIR}")
    print("=" * 70)
    
    try:
        # 1. Generar forecasts para todos los productos
        all_forecasts = generate_all_forecasts()
        
        if not all_forecasts:
            print("❌ No se pudieron generar forecasts")
            return 1
        
        # 2. Convertir a DataFrame
        df = convert_to_dataframe(all_forecasts)
        
        if df.empty:
            print("❌ DataFrame vacío")
            return 1
        
        # 3. Agregar estadísticas
        df_with_stats, sku_stats = add_summary_statistics(df)
        
        # 4. Exportar archivos de forecasts
        print("\n" + "="*70)
        print("📊 EXPORTANDO FORECASTS")
        print("="*70)
        
        files_created = export_to_csv(df_with_stats, sku_stats)
        
        # 5. Mostrar resúmenes originales
        show_forecast_overview(df)
        show_top_products(sku_stats)
        
        # 6. ANÁLISIS DE CALIDAD (Solo informativo)
        print("\n" + "="*70)
        print("📊 ANÁLISIS DE CALIDAD DE FORECASTS")
        print("="*70)
        
        # Solo mostrar estadísticas descriptivas, sin limpiar
        show_quality_analysis(df_with_stats, sku_stats)
        
        # 7. RESUMEN FINAL
        print(f"\n" + "="*70)
        print("✅ PROCESO COMPLETADO EXITOSAMENTE!")
        print("="*70)
        
        print(f"\n📁 Archivos de Forecasts:")
        for file_type, filename in files_created.items():
            print(f"   • {filename}")
        
        print(f"\n📍 Ubicación de archivos: {FORECASTS_DIR}")
        print(f"\n💡 Uso de los archivos:")
        print(f"   📊 Forecasts validados individualmente por SKU")
        print(f"   🎯 Listos para análisis de negocio y toma de decisiones")
        print(f"   ✅ Sin distorsión por limpieza global artificial")
        print(f"   📈 Cada producto respeta sus patrones históricos específicos")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
