#!/usr/bin/env python3
"""
Análisis: ¿Qué datos históricos usa SARIMA?

Este test muestra exactamente qué información del SKU desde 2016 
está utilizando SARIMA para generar el forecast.
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Constante
TARGET_SKU = "5958"

# Imports
from sales_engine.forecaster.sales_forcaster import SalesForecaster
from sales_engine.db_client import DatabaseReader

def analyze_historical_data_for_sarima(sku: str):
    """Analizar en detalle qué datos históricos usa SARIMA."""
    
    print(f"🔍 Análisis Detallado: Datos Históricos para SARIMA (SKU: {sku})")
    print("=" * 70)
    
    with SalesForecaster() as forecaster:
        # 1. Obtener datos brutos como los usa SARIMA
        print("📥 1. Datos brutos que obtiene SARIMA...")
        historical_data = forecaster.get_historical_sales_data()
        
        if historical_data is None:
            print("❌ No se pudieron obtener datos")
            return
        
        # Filtrar SKU específico
        sku_data = historical_data[historical_data['items_product_sku'] == sku].copy()
        
        print(f"   ✅ Registros totales para SKU {sku}: {len(sku_data):,}")
        print(f"   🔍 Columnas disponibles: {list(sku_data.columns)}")
        print(f"   📅 Período completo: {sku_data['issueddate'].min()} a {sku_data['issueddate'].max()}")
        
        # 2. Ver el proceso de agregación mensual
        print(f"\n📊 2. Proceso de agregación mensual...")
        monthly_data = forecaster.prepare_monthly_time_series(sku_data)
        sku_monthly = monthly_data[monthly_data['sku'] == sku].copy()
        
        print(f"   ✅ Meses con datos: {len(sku_monthly)}")
        print(f"   📊 Total cantidad agregada: {sku_monthly['total_quantity'].sum():,.0f}")
        
        # 3. Mostrar la serie temporal completa que usa SARIMA
        ts_prepared = sku_monthly[['month', 'total_quantity']].set_index('month')['total_quantity']
        ts_prepared = ts_prepared.asfreq('ME', fill_value=0)
        
        print(f"\n📈 3. Serie temporal final para SARIMA:")
        print(f"   📅 Período: {ts_prepared.index.min()} a {ts_prepared.index.max()}")
        print(f"   🗓️ Total meses: {len(ts_prepared)}")
        print(f"   📦 Promedio mensual: {ts_prepared.mean():.1f} unidades")
        print(f"   📊 Máximo mensual: {ts_prepared.max():.0f} unidades")
        print(f"   📉 Mínimo mensual: {ts_prepared.min():.0f} unidades")
        
        return sku_data, sku_monthly, ts_prepared


def show_yearly_performance(sku_data: pd.DataFrame, ts_prepared: pd.Series):
    """Mostrar rendimiento año por año que SARIMA considera."""
    
    print(f"\n📅 Rendimiento Anual del SKU {TARGET_SKU} (2016-2025)")
    print("=" * 60)
    
    # Análisis por año usando datos brutos
    sku_data['year'] = pd.to_datetime(sku_data['issueddate']).dt.year
    yearly_summary = sku_data.groupby('year').agg({
        'items_quantity': ['sum', 'count', 'mean']
    }).round(2)
    
    yearly_summary.columns = ['total_quantity', 'transactions', 'avg_per_transaction']
    
    print("📊 Resumen por Año (datos brutos):")
    print("-" * 45)
    print(" Año  | Cantidad | Trans | Prom/Trans")
    print("-" * 35)
    
    for year, row in yearly_summary.iterrows():
        print(f" {year} | {row['total_quantity']:8.0f} | {row['transactions']:5.0f} | {row['avg_per_transaction']:10.1f}")
    
    # Análisis mensual que usa SARIMA
    print(f"\n📈 Datos Mensuales que SARIMA procesa:")
    print("-" * 45)
    
    # Agrupar por año la serie temporal mensual
    ts_by_year = ts_prepared.groupby(ts_prepared.index.year).agg(['sum', 'mean', 'count', 'std'])
    ts_by_year.columns = ['total_anual', 'promedio_mensual', 'meses_con_datos', 'desviacion_std']
    
    print(" Año  | Total | Prom/Mes | Meses | Desv.Std")
    print("-" * 45)
    
    for year, row in ts_by_year.iterrows():
        print(f" {year} | {row['total_anual']:5.0f} | {row['promedio_mensual']:8.1f} | {row['meses_con_datos']:5.0f} | {row['desviacion_std']:8.1f}")


def show_monthly_patterns(ts_prepared: pd.Series):
    """Mostrar patrones mensuales que SARIMA puede detectar."""
    
    print(f"\n🔄 Patrones Estacionales que SARIMA Detecta")
    print("=" * 50)
    
    # Crear DataFrame con mes y año
    monthly_df = pd.DataFrame({
        'cantidad': ts_prepared.values,
        'mes': ts_prepared.index.month,
        'año': ts_prepared.index.year
    })
    
    # Promedio por mes del año
    monthly_avg = monthly_df.groupby('mes')['cantidad'].agg(['mean', 'std', 'count']).round(1)
    monthly_avg.index = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                        'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    print("📊 Promedio por Mes del Año (patrón estacional):")
    print("-" * 45)
    print(" Mes | Promedio | Desv.Std | Meses")
    print("-" * 35)
    
    for mes, row in monthly_avg.iterrows():
        print(f" {mes} | {row['mean']:8.1f} | {row['std']:8.1f} | {row['count']:5.0f}")
    
    # Identificar meses con patrones
    max_month = monthly_avg['mean'].idxmax()
    min_month = monthly_avg['mean'].idxmin()
    
    print(f"\n🔍 Patrones Detectados:")
    print(f"   📈 Mes con mayores ventas: {max_month} ({monthly_avg.loc[max_month, 'mean']:.1f} unidades)")
    print(f"   📉 Mes con menores ventas: {min_month} ({monthly_avg.loc[min_month, 'mean']:.1f} unidades)")
    
    # Calcular estacionalidad
    estacionalidad = (monthly_avg['mean'].max() - monthly_avg['mean'].min()) / monthly_avg['mean'].mean() * 100
    print(f"   🔄 Nivel de estacionalidad: {estacionalidad:.1f}%")


def show_recent_trends(ts_prepared: pd.Series):
    """Mostrar tendencias recientes que SARIMA considera."""
    
    print(f"\n📈 Tendencias Recientes (últimos 24 meses)")
    print("=" * 50)
    
    # Últimos 24 meses
    recent_data = ts_prepared.tail(24)
    
    print("📅 Datos de los últimos 24 meses:")
    print("-" * 35)
    print(" Mes      | Cantidad")
    print("-" * 20)
    
    for date, quantity in recent_data.items():
        print(f" {date.strftime('%Y-%m')} | {quantity:8.0f}")
    
    # Calcular tendencia
    recent_mean_12 = recent_data.tail(12).mean()
    previous_mean_12 = recent_data.head(12).mean()
    
    print(f"\n📊 Análisis de Tendencia:")
    print(f"   📉 Promedio últimos 12 meses: {recent_mean_12:.1f}")
    print(f"   📈 Promedio 12 meses anteriores: {previous_mean_12:.1f}")
    
    if recent_mean_12 > previous_mean_12:
        change = ((recent_mean_12 - previous_mean_12) / previous_mean_12) * 100
        print(f"   ↗️  Tendencia: Crecimiento del {change:.1f}%")
    else:
        change = ((previous_mean_12 - recent_mean_12) / previous_mean_12) * 100
        print(f"   ↘️  Tendencia: Reducción del {change:.1f}%")


def sarima_data_explanation():
    """Explicar exactamente qué considera SARIMA."""
    
    print(f"\n🧠 ¿Qué datos históricos considera SARIMA exactamente?")
    print("=" * 60)
    
    print("✅ SÍ considera:")
    print("   📅 TODA la historia mensual desde 2016")
    print("   📦 Cantidades vendidas por mes (agregadas)")
    print("   🔄 Patrones estacionales (mismo mes de diferentes años)")
    print("   📈 Tendencias de largo plazo")
    print("   🔗 Autocorrelación (meses pasados influyen en futuros)")
    print("   📊 Variabilidad y volatilidad histórica")
    
    print("\n❌ NO considera directamente:")
    print("   💰 Precio del producto")
    print("   💵 Ingresos totales")
    print("   👥 Información de clientes específicos")
    print("   🏪 Canales de venta individuales")
    print("   📱 Variables externas (marketing, competencia, etc.)")
    
    print("\n🎯 Lo que SARIMA aprende del histórico:")
    print("   1. 🔄 ¿Hay meses del año con más/menos ventas?")
    print("   2. 📈 ¿Las ventas están creciendo/decreciendo a largo plazo?")
    print("   3. 🔗 ¿Las ventas de un mes predicen el siguiente?")
    print("   4. 📊 ¿Qué tan variable es la demanda?")
    print("   5. 🎪 ¿Hay ciclos o patrones repetitivos?")


def main():
    """Análisis principal de datos históricos para SARIMA."""
    
    print("🔍 Análisis: Datos Históricos que Usa SARIMA")
    print("=" * 60)
    print(f"🎯 SKU: {TARGET_SKU}")
    
    try:
        # 1. Analizar datos históricos
        result = analyze_historical_data_for_sarima(TARGET_SKU)
        
        if result:
            sku_data, sku_monthly, ts_prepared = result
            
            # 2. Mostrar rendimiento anual
            show_yearly_performance(sku_data, ts_prepared)
            
            # 3. Mostrar patrones estacionales
            show_monthly_patterns(ts_prepared)
            
            # 4. Mostrar tendencias recientes
            show_recent_trends(ts_prepared)
            
            # 5. Explicación de qué considera SARIMA
            sarima_data_explanation()
            
            print(f"\n✅ Análisis completado para SKU {TARGET_SKU}!")
        else:
            print("❌ No se pudieron obtener datos para análisis")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 