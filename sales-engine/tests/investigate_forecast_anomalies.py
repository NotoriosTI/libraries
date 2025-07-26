#!/usr/bin/env python3
"""
Investigación de Anomalías en Forecasts

Analiza por qué productos con 0 ventas tienen forecasts tan altos.
Revisa datos históricos, modelos y lógica de forecasting.
"""

import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import numpy as np

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sales_engine.db_client import DatabaseReader, ForecastReader


def investigate_sku_anomalies(problematic_skus: list, year: int = 2024, month: int = 1):
    """
    Investigar SKUs específicos que tienen forecasts altos pero 0 ventas.
    
    Args:
        problematic_skus (list): Lista de SKUs problemáticos
        year (int): Año de las ventas a analizar
        month (int): Mes de las ventas a analizar
    """
    print("🔍 INVESTIGACIÓN DE ANOMALÍAS EN FORECASTS")
    print("=" * 60)
    
    db_reader = DatabaseReader()
    forecast_reader = ForecastReader()
    
    for sku in problematic_skus:
        print(f"\n🎯 ANALIZANDO SKU: {sku}")
        print("-" * 50)
        
        try:
            # 1. Obtener forecast actual
            forecast_data = forecast_reader.get_forecast_for_sku(sku, month)
            if forecast_data:
                current_forecast = forecast_data.get('total_quantity', 0)
                print(f"📈 Forecast para mes {month}: {current_forecast:.1f} unidades")
            else:
                print(f"📈 No se encontró forecast para SKU {sku}")
                continue
            
            # 2. Obtener ventas del mes específico
            month_sales = get_sku_sales_for_month(db_reader, sku, year, month)
            print(f"📊 Ventas en {year}-{month:02d}: {month_sales:.1f} unidades")
            
                         # 3. Obtener historial completo de ventas
            historical_sales = get_sku_historical_sales(db_reader, sku)
            if not historical_sales.empty:
                # Convertir issueddate a datetime si es string
                if historical_sales['issueddate'].dtype == 'object':
                    historical_sales['issueddate'] = pd.to_datetime(historical_sales['issueddate'])
                
                print(f"📅 Datos históricos: {len(historical_sales)} registros")
                print(f"   Período: {historical_sales['issueddate'].min().date()} a {historical_sales['issueddate'].max().date()}")
                print(f"   Total histórico: {historical_sales['items_quantity'].sum():.1f} unidades")
                
                # Análisis por meses
                monthly_sales = historical_sales.groupby(historical_sales['issueddate'].dt.to_period('M'))['items_quantity'].sum()
                print(f"   Meses con ventas: {len(monthly_sales[monthly_sales > 0])}")
                print(f"   Meses sin ventas: {len(monthly_sales[monthly_sales == 0])}")
                print(f"   Promedio mensual: {monthly_sales.mean():.1f} unidades")
                
                if len(monthly_sales) > 0:
                    print(f"   Ventas máximas en un mes: {monthly_sales.max():.1f}")
                    print(f"   Ventas promedio (meses con ventas): {monthly_sales[monthly_sales > 0].mean():.1f}")
                
                # 🚨 ANÁLISIS CRÍTICO: ¿Cuándo fue la última venta?
                last_sale_date = historical_sales['issueddate'].max()
                days_since_last_sale = (datetime.now().date() - last_sale_date.date()).days
                print(f"🕒 Última venta: {last_sale_date.date()} ({days_since_last_sale} días atrás)")
                
                if days_since_last_sale > 365:
                    print("   🚨 PRODUCTO POSIBLEMENTE DESCONTINUADO (sin ventas por >1 año)")
                elif days_since_last_sale > 180:
                    print("   ⚠️  PRODUCTO INACTIVO (sin ventas por >6 meses)")
                    
                # Análisis de tendencia reciente
                recent_sales = historical_sales[historical_sales['issueddate'] >= (datetime.now() - pd.DateOffset(years=2))]
                if not recent_sales.empty:
                    print(f"   📊 Ventas últimos 2 años: {recent_sales['items_quantity'].sum():.1f} unidades")
                else:
                    print("   📊 Ventas últimos 2 años: 0 unidades")
            else:
                print(f"❌ No se encontraron datos históricos para SKU {sku}")
            
            # 4. Buscar patrones estacionales
            if not historical_sales.empty:
                seasonal_analysis = analyze_seasonality(historical_sales, sku)
                
            # 5. Verificar si es producto nuevo
            first_sale = historical_sales['issueddate'].min() if not historical_sales.empty else None
            if first_sale:
                days_since_first_sale = (datetime.now().date() - first_sale.date()).days
                print(f"🎬 Primer venta: {first_sale.date()} ({days_since_first_sale} días atrás)")
                if days_since_first_sale < 365:
                    print("   🆕 PRODUCTO RELATIVAMENTE NUEVO")
            
        except Exception as e:
            print(f"❌ Error analizando SKU {sku}: {e}")


def get_sku_sales_for_month(db_reader: DatabaseReader, sku: str, year: int, month: int) -> float:
    """Obtener ventas de un SKU específico para un mes."""
    from calendar import monthrange
    start_date = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    sales_data = db_reader.get_sales_data(
        start_date=start_date,
        end_date=end_date,
        product_skus=[sku]
    )
    
    if sales_data.empty or 'items_quantity' not in sales_data.columns:
        return 0.0
    
    return sales_data['items_quantity'].sum()


def get_sku_historical_sales(db_reader: DatabaseReader, sku: str) -> pd.DataFrame:
    """Obtener todo el historial de ventas de un SKU."""
    try:
        sales_data = db_reader.get_sales_data(product_skus=[sku])
        return sales_data
    except Exception as e:
        print(f"Error obteniendo historial para {sku}: {e}")
        return pd.DataFrame()


def analyze_seasonality(historical_sales: pd.DataFrame, sku: str):
    """Analizar patrones estacionales en las ventas."""
    try:
        historical_sales['month'] = historical_sales['issueddate'].dt.month
        monthly_totals = historical_sales.groupby('month')['items_quantity'].sum()
        
        print(f"🌍 Análisis estacional para {sku}:")
        for month_num, total in monthly_totals.items():
            month_names = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                          'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            print(f"   {month_names[month_num]}: {total:.1f} unidades")
        
        # Detectar estacionalidad
        if len(monthly_totals) >= 3:
            max_month = monthly_totals.idxmax()
            max_value = monthly_totals.max()
            min_value = monthly_totals.min()
            
            if max_value > min_value * 3:
                print(f"   🎯 ALTA ESTACIONALIDAD detectada (máx en mes {max_month})")
            
    except Exception as e:
        print(f"   Error en análisis estacional: {e}")


def investigate_forecast_logic():
    """Investigar la lógica general del sistema de forecasting."""
    print(f"\n🧠 INVESTIGACIÓN DE LÓGICA DE FORECASTING")
    print("=" * 60)
    
    try:
        forecast_reader = ForecastReader()
        
        # Obtener estadísticas generales de forecasts
        print("📊 Estadísticas generales de forecasts:")
        
        # Esta función necesitaría implementarse en ForecastReader
        # Por ahora, simular con una consulta directa
        
    except Exception as e:
        print(f"❌ Error investigando lógica: {e}")


def main():
    """Función principal de investigación."""
    
    # SKUs problemáticos identificados en el análisis anterior
    problematic_skus = [
        "6912",  # Forecast 403, Ventas 28, Stock 0
        "6028",  # Forecast 222, Ventas 0, Stock 0  
        "6406",  # Forecast 194, Ventas 0, Stock 0
        "7063",  # Forecast 153, Ventas 0, Stock 0
        "6845",  # Forecast 122, Ventas 0, Stock 0
    ]
    
    print("🚨 INVESTIGACIÓN: ¿Por qué productos con 0 ventas tienen forecasts altos?")
    print("=" * 80)
    
    # Investigar SKUs específicos
    investigate_sku_anomalies(problematic_skus, 2024, 1)
    
    # Investigar lógica general
    investigate_forecast_logic()
    
    # Conclusiones y recomendaciones
    print(f"\n💡 POSIBLES CAUSAS Y RECOMENDACIONES:")
    print("=" * 60)
    print("1. 📈 Modelo SARIMA interpretando tendencias incorrectas")
    print("2. 🔢 Relleno de datos con 0s creando patrones artificiales")
    print("3. 🆕 Productos nuevos sin suficiente historial")
    print("4. 🏷️  Posible agrupación incorrecta de SKUs similares")
    print("5. 📊 Estacionalidad detectada incorrectamente")
    print("\n🔧 RECOMENDACIONES:")
    print("- Validar productos nuevos vs establecidos")
    print("- Aplicar filtros más estrictos para productos sin historial")
    print("- Revisar parámetros del modelo SARIMA")
    print("- Implementar forecast mínimo basado en ventas reales")


if __name__ == "__main__":
    main() 