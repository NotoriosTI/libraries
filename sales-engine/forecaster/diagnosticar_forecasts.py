#!/usr/bin/env python3
"""
Script de Diagnóstico para Forecasts Problemáticos

Este script analiza los datos de ventas y identifica las causas raíz
de los valores extremos en los forecasts SARIMA.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date, timedelta

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sales_engine.db_client.sales_forcaster import SalesForecaster

def analizar_datos_historicos():
    """Analizar calidad de datos históricos."""
    
    print("🔍 Analizando Datos Históricos")
    print("=" * 50)
    
    try:
        with SalesForecaster() as forecaster:
            # Obtener datos históricos
            historical_data = forecaster.get_historical_sales_data()
            
            if historical_data is None:
                print("❌ No se pudieron obtener datos históricos")
                return
            
            print(f"📊 Total registros históricos: {len(historical_data):,}")
            print(f"📅 Rango de fechas: {historical_data['issueddate'].min()} a {historical_data['issueddate'].max()}")
            print(f"📦 SKUs únicos: {historical_data['items_product_sku'].nunique():,}")
            
            # Preparar datos mensuales
            monthly_data = forecaster.prepare_monthly_time_series(historical_data)
            
            print(f"\n📈 Datos agregados mensuales:")
            print(f"   📊 Registros mensuales: {len(monthly_data):,}")
            print(f"   📦 SKUs únicos: {monthly_data['sku'].nunique():,}")
            
            # Analizar distribución de cantidades
            quantities = monthly_data['total_quantity']
            
            print(f"\n📊 Distribución de Cantidades Mensuales:")
            print(f"   Media: {quantities.mean():.2f}")
            print(f"   Mediana: {quantities.median():.2f}")
            print(f"   Desv. Estándar: {quantities.std():.2f}")
            print(f"   Mínimo: {quantities.min()}")
            print(f"   Máximo: {quantities.max():,}")
            print(f"   Q95: {quantities.quantile(0.95):,.0f}")
            print(f"   Q99: {quantities.quantile(0.99):,.0f}")
            
            # Identificar SKUs problemáticos
            print(f"\n🔍 Análisis de SKUs Problemáticos:")
            
            problematic_skus = []
            high_variance_skus = []
            sparse_skus = []
            
            for sku in monthly_data['sku'].unique():
                sku_data = monthly_data[monthly_data['sku'] == sku]['total_quantity']
                
                # Verificar valores extremos
                if sku_data.max() > 100000:
                    problematic_skus.append((sku, sku_data.max(), sku_data.std()))
                
                # Verificar alta variabilidad
                if len(sku_data) > 5 and sku_data.std() > sku_data.mean() * 5:
                    high_variance_skus.append((sku, sku_data.mean(), sku_data.std()))
                
                # Verificar series dispersas
                zero_count = (sku_data == 0).sum()
                if len(sku_data) > 10 and zero_count / len(sku_data) > 0.8:
                    sparse_skus.append((sku, zero_count, len(sku_data)))
            
            print(f"   🔴 SKUs con valores extremos (>100K): {len(problematic_skus)}")
            if problematic_skus:
                print("   Top 5 SKUs con valores más altos:")
                for sku, max_val, std_val in sorted(problematic_skus, key=lambda x: x[1], reverse=True)[:5]:
                    print(f"      {sku}: max={max_val:,}, std={std_val:.1f}")
            
            print(f"   ⚡ SKUs con alta variabilidad: {len(high_variance_skus)}")
            if high_variance_skus:
                print("   Top 5 SKUs más variables:")
                for sku, mean_val, std_val in sorted(high_variance_skus, key=lambda x: x[2], reverse=True)[:5]:
                    print(f"      {sku}: mean={mean_val:.1f}, std={std_val:.1f}, ratio={std_val/mean_val:.1f}")
            
            print(f"   🕳️  SKUs dispersos (>80% ceros): {len(sparse_skus)}")
            if sparse_skus:
                print("   Top 5 SKUs más dispersos:")
                for sku, zeros, total in sorted(sparse_skus, key=lambda x: x[1]/x[2], reverse=True)[:5]:
                    print(f"      {sku}: {zeros}/{total} ceros ({zeros/total:.1%})")
            
            return {
                'historical_data': historical_data,
                'monthly_data': monthly_data,
                'problematic_skus': problematic_skus,
                'high_variance_skus': high_variance_skus,
                'sparse_skus': sparse_skus
            }
            
    except Exception as e:
        print(f"❌ Error analizando datos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def analizar_sku_especifico(sku, monthly_data):
    """Analizar un SKU específico en detalle."""
    
    print(f"\n🔬 Análisis Detallado del SKU: {sku}")
    print("=" * 50)
    
    sku_data = monthly_data[monthly_data['sku'] == sku]
    
    if sku_data.empty:
        print(f"❌ No se encontraron datos para el SKU {sku}")
        return
    
    ts = sku_data[['month', 'total_quantity']].set_index('month')['total_quantity']
    ts = ts.resample('ME').sum().fillna(0)
    
    print(f"📊 Estadísticas del SKU {sku}:")
    print(f"   Período: {ts.index.min()} a {ts.index.max()}")
    print(f"   Total meses: {len(ts)}")
    print(f"   Meses con ventas: {(ts > 0).sum()}")
    print(f"   Meses sin ventas: {(ts == 0).sum()}")
    print(f"   Total vendido: {ts.sum():,}")
    print(f"   Promedio mensual: {ts.mean():.2f}")
    print(f"   Mediana: {ts.median():.2f}")
    print(f"   Desv. Estándar: {ts.std():.2f}")
    print(f"   Mínimo: {ts.min()}")
    print(f"   Máximo: {ts.max():,}")
    
    # Mostrar últimos 12 meses
    print(f"\n📅 Últimos 12 meses:")
    recent_data = ts.tail(12)
    for date, quantity in recent_data.items():
        print(f"   {date.strftime('%Y-%m')}: {quantity:,}")

def main():
    """Función principal de diagnóstico."""
    
    print("🩺 Diagnóstico de Forecasts Extremos")
    print("=" * 60)
    
    # Analizar datos históricos
    analysis_results = analizar_datos_historicos()
    
    if not analysis_results:
        print("❌ No se pudo completar el análisis")
        return 1
    
    # Analizar SKUs más problemáticos
    if analysis_results['problematic_skus']:
        print(f"\n🔬 Análisis Detallado de SKUs Problemáticos")
        print("=" * 60)
        
        # Analizar los 3 SKUs más problemáticos
        top_problematic = sorted(analysis_results['problematic_skus'], 
                               key=lambda x: x[1], reverse=True)[:3]
        
        for sku, max_val, std_val in top_problematic:
            analizar_sku_especifico(sku, analysis_results['monthly_data'])
    
    # Recomendaciones
    print(f"\n💡 Recomendaciones:")
    print("=" * 30)
    print("1. 🔧 Actualiza el código con las mejoras implementadas")
    print("2. 🧹 Aplica límites más estrictos (ej: max 10,000 unidades)")
    print("3. 📊 Considera modelos más simples para SKUs irregulares")
    print("4. ⚡ Implementa selección automática de parámetros SARIMA")
    print("5. 🎯 Usa métodos de forecast más robustos (ej: Prophet, ETS)")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 