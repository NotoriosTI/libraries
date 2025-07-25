#!/usr/bin/env python3
"""
Test Comparativo: SARIMA vs Regresión Lineal para Forecast

Compara ambos métodos para el mismo SKU y evalúa cuál es mejor.
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Constante a nivel de módulo
TARGET_SKU = "5958"

# Imports
from sales_engine.forecaster.sales_forcaster import SalesForecaster
from sales_engine.db_client import DatabaseReader

class LinearRegressionForecaster:
    """Forecaster simple basado en regresión lineal."""
    
    def __init__(self, sku: str):
        self.sku = sku
        self.model = LinearRegression()
        self.fitted = False
        
    def prepare_data(self) -> pd.Series:
        """Obtener y preparar datos mensuales desde 2016."""
        print(f"📊 Obteniendo datos para regresión lineal (SKU: {self.sku})")
        
        with DatabaseReader() as db:
            # Datos desde 2016 (inicio de la empresa)
            start_date = date(2016, 1, 1)
            end_date = date.today()
            
            data = db.get_sales_data(
                start_date=start_date,
                end_date=end_date,
                product_skus=[self.sku]
            )
            
            if data.empty:
                return pd.Series()
            
            # Convertir a serie temporal mensual
            data['issueddate'] = pd.to_datetime(data['issueddate'])
            data.set_index('issueddate', inplace=True)
            
            # Agrupar por mes y sumar cantidades
            monthly_sales = data['items_quantity'].resample('ME').sum()
            
            print(f"   ✅ {len(monthly_sales)} meses de datos desde {monthly_sales.index.min()} hasta {monthly_sales.index.max()}")
            print(f"   📦 Total vendido: {monthly_sales.sum():,.0f} unidades")
            print(f"   📊 Promedio mensual: {monthly_sales.mean():.1f} unidades")
            
            return monthly_sales
    
    def fit(self, monthly_sales: pd.Series):
        """Entrenar modelo de regresión lineal."""
        if monthly_sales.empty:
            raise ValueError("No hay datos para entrenar")
        
        # Preparar datos para regresión
        # X = número de mes desde el inicio (0, 1, 2, ...)
        # Y = ventas mensuales
        X = np.arange(len(monthly_sales)).reshape(-1, 1)
        y = monthly_sales.values
        
        # Entrenar modelo
        self.model.fit(X, y)
        self.fitted = True
        self.n_months = len(monthly_sales)  # Guardar cantidad de meses para forecast
        
        # Estadísticas del ajuste
        y_pred = self.model.predict(X)
        r2_score = self.model.score(X, y)
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        
        print(f"📈 Modelo de regresión lineal entrenado:")
        print(f"   📊 R² Score: {r2_score:.3f}")
        print(f"   📏 MAE: {mae:.1f} unidades")
        print(f"   📐 RMSE: {rmse:.1f} unidades")
        print(f"   📈 Pendiente: {self.model.coef_[0]:.2f} unidades/mes")
        print(f"   📍 Intercepto: {self.model.intercept_:.1f} unidades")
        
        return {
            'r2': r2_score,
            'mae': mae,
            'rmse': rmse,
            'slope': self.model.coef_[0],
            'intercept': self.model.intercept_
        }
    
    def forecast(self, steps: int = 12) -> pd.Series:
        """Generar forecast de regresión lineal."""
        if not self.fitted:
            raise ValueError("Modelo no entrenado")
        
        # Generar números de mes para el futuro
        last_month_num = self.n_months - 1  # Último mes usado en entrenamiento
        future_months = np.arange(last_month_num + 1, last_month_num + 1 + steps).reshape(-1, 1)
        
        # Predecir
        predictions = self.model.predict(future_months)
        
        # Crear fechas futuras
        last_date = pd.Timestamp.now().replace(day=1) + pd.DateOffset(months=1)
        future_dates = pd.date_range(start=last_date, periods=steps, freq='ME')
        
        # Asegurar valores no negativos
        predictions = np.maximum(predictions, 0)
        
        return pd.Series(predictions.round().astype(int), index=future_dates)


def test_sarima_forecast(sku: str) -> tuple:
    """Generar forecast usando SARIMA."""
    print(f"\n🔮 Forecast SARIMA para SKU: {sku}")
    print("=" * 45)
    
    with SalesForecaster() as forecaster:
        historical_data = forecaster.get_historical_sales_data()
        
        if historical_data is None:
            return None, None
        
        sku_data = historical_data[historical_data['items_product_sku'] == sku].copy()
        
        if sku_data.empty:
            return None, None
        
        monthly_data = forecaster.prepare_monthly_time_series(sku_data)
        sku_monthly = monthly_data[monthly_data['sku'] == sku]
        
        ts_prepared = sku_monthly[['month', 'total_quantity']].set_index('month')['total_quantity']
        ts_prepared = ts_prepared.asfreq('ME', fill_value=0)
        
        forecast_result = forecaster._forecast_single_sku(ts_prepared, steps=12)
        
        if forecast_result is None:
            return None, None
        
        print(f"✅ SARIMA forecast generado ({len(forecast_result)} meses)")
        return forecast_result, ts_prepared


def test_linear_forecast(sku: str) -> tuple:
    """Generar forecast usando regresión lineal."""
    print(f"\n📈 Forecast Regresión Lineal para SKU: {sku}")
    print("=" * 50)
    
    forecaster = LinearRegressionForecaster(sku)
    monthly_sales = forecaster.prepare_data()
    
    if monthly_sales.empty:
        return None, None
    
    stats = forecaster.fit(monthly_sales)
    forecast_result = forecaster.forecast(steps=12)
    
    print(f"✅ Regresión lineal forecast generado ({len(forecast_result)} meses)")
    
    return forecast_result, monthly_sales, stats


def compare_forecasts(sarima_forecast, linear_forecast, historical_data):
    """Comparar ambos métodos de forecast."""
    print(f"\n⚖️  Comparación de Métodos de Forecast")
    print("=" * 55)
    
    if sarima_forecast is None or linear_forecast is None:
        print("❌ No se pueden comparar - falta algún forecast")
        return
    
    # Estadísticas básicas
    sarima_total = sarima_forecast.sum()
    linear_total = linear_forecast.sum()
    sarima_avg = sarima_forecast.mean()
    linear_avg = linear_forecast.mean()
    
    historical_avg = historical_data.mean() if historical_data is not None else 0
    
    print(f"📊 Resumen de Forecasts (12 meses):")
    print("-" * 40)
    print(f"🔮 SARIMA:")
    print(f"   📦 Total: {sarima_total:,.0f} unidades")
    print(f"   📊 Promedio: {sarima_avg:.1f} unidades/mes")
    print(f"   📈 vs Histórico: {((sarima_avg/historical_avg - 1)*100):+.1f}%")
    
    print(f"\n📈 Regresión Lineal:")
    print(f"   📦 Total: {linear_total:,.0f} unidades")
    print(f"   📊 Promedio: {linear_avg:.1f} unidades/mes")
    print(f"   📈 vs Histórico: {((linear_avg/historical_avg - 1)*100):+.1f}%")
    
    # Diferencias entre métodos
    diff_total = abs(sarima_total - linear_total)
    diff_avg = abs(sarima_avg - linear_avg)
    
    print(f"\n🔍 Diferencias entre Métodos:")
    print("-" * 30)
    print(f"📦 Diferencia total: {diff_total:,.0f} unidades")
    print(f"📊 Diferencia promedio: {diff_avg:.1f} unidades/mes")
    print(f"📈 Diferencia relativa: {(diff_avg/historical_avg*100):.1f}% del histórico")
    
    # Mes a mes
    print(f"\n📅 Comparación Mes a Mes:")
    print("-" * 25)
    print(" Mes      | SARIMA | Linear | Diff  ")
    print("-" * 35)
    
    for i, (sarima_val, linear_val) in enumerate(zip(sarima_forecast, linear_forecast), 1):
        diff = abs(sarima_val - linear_val)
        print(f" {i:2}       | {sarima_val:6.0f} | {linear_val:6.0f} | {diff:5.0f}")


def evaluate_methods():
    """Evaluación conceptual de ambos métodos."""
    print(f"\n🎯 Evaluación de Métodos para Sales Forecasting")
    print("=" * 55)
    
    print("📊 SARIMA (Seasonal AutoRegressive Integrated Moving Average):")
    print("   ✅ Ventajas:")
    print("      🔄 Captura patrones estacionales (ej: ventas altas en diciembre)")
    print("      📈 Maneja tendencias complejas (no lineales)")
    print("      🔗 Considera autocorrelación (ventas pasadas → futuras)")
    print("      🎯 Mayor precisión en series complejas")
    print("   ❌ Desventajas:")
    print("      🧠 Complejo de entender e interpretar")
    print("      📊 Requiere muchos datos (mínimo 24 meses)")
    print("      ⚡ Computacionalmente costoso")
    print("      🔧 Difícil de ajustar parámetros")
    
    print("\n📈 Regresión Lineal:")
    print("   ✅ Ventajas:")
    print("      💡 Simple y fácil de entender")
    print("      ⚡ Muy rápido de calcular")
    print("      📋 Fácil de interpretar (pendiente = crecimiento)")
    print("      📊 Funciona con pocos datos")
    print("   ❌ Desventajas:")
    print("      📅 NO captura estacionalidad")
    print("      📏 Solo tendencias lineales")
    print("      🎯 Menor precisión en series complejas")
    print("      📉 Ignora patrones cíclicos")
    
    print(f"\n💡 Recomendación para SKU {TARGET_SKU}:")
    print("-" * 35)
    print("🔮 SARIMA es mejor SI:")
    print("   • Hay patrones estacionales claros")
    print("   • Tienes >24 meses de datos")
    print("   • Precisión es crítica")
    print("   • Puedes tolerar complejidad")
    
    print("\n📈 Regresión Lineal es mejor SI:")
    print("   • Quieres simplicidad y rapidez")
    print("   • Necesitas explicar el modelo fácilmente")
    print("   • Los datos son limitados")
    print("   • La tendencia es principalmente lineal")


def main():
    """Test comparativo principal."""
    print("🧪 Test Comparativo: SARIMA vs Regresión Lineal")
    print("=" * 60)
    print(f"🎯 SKU objetivo: {TARGET_SKU}")
    
    try:
        # 1. Forecast SARIMA
        sarima_result = test_sarima_forecast(TARGET_SKU)
        sarima_forecast, sarima_historical = sarima_result if sarima_result[0] is not None else (None, None)
        
        # 2. Forecast Regresión Lineal  
        linear_result = test_linear_forecast(TARGET_SKU)
        if len(linear_result) == 3:
            linear_forecast, linear_historical, linear_stats = linear_result
        else:
            linear_forecast, linear_historical = linear_result if linear_result[0] is not None else (None, None)
        
        # 3. Comparar resultados
        if sarima_forecast is not None and linear_forecast is not None:
            compare_forecasts(sarima_forecast, linear_forecast, sarima_historical)
        
        # 4. Evaluación conceptual
        evaluate_methods()
        
        print(f"\n✅ Comparación completada para SKU {TARGET_SKU}!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 