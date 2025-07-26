#!/usr/bin/env python3
"""
Detector y Corrector de Forecasts de Productos Descontinuados

Este script identifica productos que probablemente están descontinuados
y propone correcciones para sus forecasts.
"""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sales_engine.db_client import DatabaseReader, ForecastReader


def detect_discontinued_products(months_threshold: int = 12, min_forecast: float = 50):
    """
    Detectar productos que probablemente están descontinuados.
    
    Args:
        months_threshold (int): Meses sin ventas para considerar descontinuado
        min_forecast (float): Forecast mínimo para considerar problemático
    
    Returns:
        pd.DataFrame: Lista de productos descontinuados con forecasts altos
    """
    print("🔍 DETECCIÓN DE PRODUCTOS DESCONTINUADOS CON FORECASTS ALTOS")
    print("=" * 70)
    
    db_reader = DatabaseReader()
    forecast_reader = ForecastReader()
    
    # 1. Obtener todos los forecasts para enero
    forecasts = forecast_reader.get_forecasts_by_month(1)
    
    # 2. Filtrar solo forecasts significativos
    high_forecasts = {sku: qty for sku, qty in forecasts.items() if qty >= min_forecast}
    
    print(f"📊 Analizando {len(high_forecasts)} productos con forecast >= {min_forecast} unidades...")
    
    discontinued_products = []
    threshold_date = datetime.now() - timedelta(days=months_threshold * 30)
    
    for sku, forecast_qty in high_forecasts.items():
        try:
            # Obtener historial de ventas
            historical_sales = db_reader.get_sales_data(product_skus=[sku])
            
            if historical_sales.empty:
                # Sin historial = producto fantasma
                discontinued_products.append({
                    'sku': sku,
                    'forecast': forecast_qty,
                    'status': 'SIN_HISTORIAL',
                    'last_sale': None,
                    'days_since_last_sale': None,
                    'total_historical': 0,
                    'recent_sales': 0
                })
                continue
            
            # Convertir fechas
            if historical_sales['issueddate'].dtype == 'object':
                historical_sales['issueddate'] = pd.to_datetime(historical_sales['issueddate'])
            
            # Análisis temporal
            last_sale_date = historical_sales['issueddate'].max()
            days_since_last_sale = (datetime.now().date() - last_sale_date.date()).days
            
            # Ventas recientes (últimos 2 años)
            recent_sales = historical_sales[
                historical_sales['issueddate'] >= (datetime.now() - pd.DateOffset(years=2))
            ]
            recent_total = recent_sales['items_quantity'].sum() if not recent_sales.empty else 0
            
            # Clasificar estado
            status = 'ACTIVO'
            if days_since_last_sale > months_threshold * 30:
                status = 'DESCONTINUADO'
            elif days_since_last_sale > 180:
                status = 'INACTIVO'
            elif recent_total == 0:
                status = 'SIN_VENTAS_RECIENTES'
            
            # Solo incluir productos problemáticos
            if status != 'ACTIVO':
                discontinued_products.append({
                    'sku': sku,
                    'forecast': forecast_qty,
                    'status': status,
                    'last_sale': last_sale_date.date(),
                    'days_since_last_sale': days_since_last_sale,
                    'total_historical': historical_sales['items_quantity'].sum(),
                    'recent_sales': recent_total
                })
                
        except Exception as e:
            print(f"   ⚠️  Error analizando SKU {sku}: {e}")
            continue
    
    # Crear DataFrame y ordenar
    df_discontinued = pd.DataFrame(discontinued_products)
    if not df_discontinued.empty:
        df_discontinued = df_discontinued.sort_values('forecast', ascending=False)
    
    return df_discontinued


def propose_forecast_corrections(discontinued_df: pd.DataFrame) -> pd.DataFrame:
    """
    Proponer correcciones para los forecasts de productos descontinuados.
    
    Args:
        discontinued_df (pd.DataFrame): DataFrame de productos descontinuados
    
    Returns:
        pd.DataFrame: DataFrame con correcciones propuestas
    """
    print(f"\n💡 PROPUESTA DE CORRECCIONES")
    print("=" * 50)
    
    corrections = []
    
    for _, row in discontinued_df.iterrows():
        sku = row['sku']
        current_forecast = row['forecast']
        status = row['status']
        
        # Lógica de corrección basada en estado
        if status == 'SIN_HISTORIAL':
            proposed_forecast = 0
            reason = "Sin historial de ventas"
            
        elif status == 'DESCONTINUADO':
            proposed_forecast = 0
            reason = f"Sin ventas por {row['days_since_last_sale']} días"
            
        elif status == 'INACTIVO':
            # Reducir drásticamente pero no a 0 (por si acaso)
            proposed_forecast = min(5, current_forecast * 0.1)
            reason = f"Inactivo por {row['days_since_last_sale']} días"
            
        elif status == 'SIN_VENTAS_RECIENTES':
            # Usar promedio histórico muy conservador
            if row['total_historical'] > 0:
                # Asumir vida útil de 4 años, promedio mensual muy conservador
                proposed_forecast = max(1, row['total_historical'] / (4 * 12) * 0.5)
            else:
                proposed_forecast = 0
            reason = "Sin ventas últimos 2 años, usar histórico conservador"
        
        else:
            proposed_forecast = current_forecast
            reason = "Mantener"
        
        # Redondear
        proposed_forecast = round(proposed_forecast, 1)
        
        corrections.append({
            'sku': sku,
            'current_forecast': current_forecast,
            'proposed_forecast': proposed_forecast,
            'reduction': current_forecast - proposed_forecast,
            'reduction_pct': ((current_forecast - proposed_forecast) / current_forecast * 100) if current_forecast > 0 else 0,
            'status': status,
            'reason': reason
        })
    
    return pd.DataFrame(corrections)


def main():
    """Función principal."""
    
    print("🏭 ANÁLISIS Y CORRECCIÓN DE FORECASTS DE PRODUCTOS DESCONTINUADOS")
    print("=" * 80)
    
    # 1. Detectar productos descontinuados
    discontinued_df = detect_discontinued_products(months_threshold=12, min_forecast=50)
    
    if discontinued_df.empty:
        print("✅ No se encontraron productos descontinuados con forecasts altos")
        return
    
    # 2. Mostrar resumen
    print(f"\n📋 RESUMEN DE PRODUCTOS PROBLEMÁTICOS:")
    print("-" * 60)
    print(f"   Total productos con forecast alto: {len(discontinued_df)}")
    
    status_counts = discontinued_df['status'].value_counts()
    for status, count in status_counts.items():
        print(f"   {status}: {count} productos")
    
    total_forecast_waste = discontinued_df['forecast'].sum()
    print(f"   Total forecast desperdiciado: {total_forecast_waste:,.1f} unidades")
    
    # 3. Mostrar top problemáticos
    print(f"\n🚨 TOP 10 PRODUCTOS MÁS PROBLEMÁTICOS:")
    print("-" * 80)
    print(f"{'SKU':<8} {'Forecast':<10} {'Estado':<20} {'Días sin venta':<15} {'Última venta':<12}")
    print("-" * 80)
    
    for _, row in discontinued_df.head(10).iterrows():
        last_sale = row['last_sale'].strftime('%Y-%m-%d') if row['last_sale'] else 'Nunca'
        days = str(row['days_since_last_sale']) if row['days_since_last_sale'] else 'N/A'
        print(f"{row['sku']:<8} {row['forecast']:<10.1f} {row['status']:<20} {days:<15} {last_sale:<12}")
    
    # 4. Proponer correcciones
    corrections_df = propose_forecast_corrections(discontinued_df)
    
    print(f"\n💰 IMPACTO DE CORRECCIONES PROPUESTAS:")
    print("-" * 60)
    
    total_reduction = corrections_df['reduction'].sum()
    total_current = corrections_df['current_forecast'].sum()
    reduction_pct = (total_reduction / total_current * 100) if total_current > 0 else 0
    
    print(f"   Forecast actual total: {total_current:,.1f} unidades")
    print(f"   Reducción propuesta: {total_reduction:,.1f} unidades ({reduction_pct:.1f}%)")
    print(f"   Forecast corregido: {total_current - total_reduction:,.1f} unidades")
    
    # 5. Mostrar correcciones detalladas
    print(f"\n🔧 CORRECCIONES DETALLADAS (Top 15):")
    print("-" * 90)
    print(f"{'SKU':<8} {'Actual':<8} {'Propuesto':<10} {'Reducción':<10} {'%':<6} {'Razón':<35}")
    print("-" * 90)
    
    for _, row in corrections_df.head(15).iterrows():
        print(f"{row['sku']:<8} {row['current_forecast']:<8.1f} {row['proposed_forecast']:<10.1f} "
              f"{row['reduction']:<10.1f} {row['reduction_pct']:<6.1f} {row['reason']:<35}")
    
    # 6. Recomendaciones
    print(f"\n🎯 RECOMENDACIONES:")
    print("=" * 50)
    print("1. 🛑 Implementar filtro de productos descontinuados en el forecaster")
    print("2. 📅 Agregar validación de 'última venta' antes de generar forecast")
    print("3. 🔄 Revisar mensualmente productos sin ventas por >6 meses")
    print("4. 🏷️  Marcar productos como 'DESCONTINUADO' en el catálogo")
    print("5. 📊 Usar forecasts conservadores para productos inactivos")
    print("6. 🧹 Limpiar datos históricos de productos fantasma")
    
    return discontinued_df, corrections_df


if __name__ == "__main__":
    discontinued_df, corrections_df = main() 