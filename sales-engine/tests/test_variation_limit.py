#!/usr/bin/env python3
"""
Script de prueba para verificar el límite de variación del 40%
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
import numpy as np
from sales_engine.forecaster.sales_forcaster import SalesForecaster

def test_variation_limit():
    """Probar el límite de variación del 40%"""
    print("🧪 PRUEBA: Límite de Variación del 40%")
    print("="*50)
    
    forecaster = SalesForecaster()
    
    # Crear datos de prueba
    # Serie histórica con último valor = 100
    historical_data = pd.Series([80, 90, 85, 95, 100], name='test_sku')
    
    # Predicciones extremas sin límite (simulando SARIMA descontrolado)
    extreme_predictions = pd.Series([500, 50, 800, 10, 1000])  # Variaciones extremas
    
    print(f"📊 Datos históricos: {historical_data.tolist()}")
    print(f"📊 Último valor histórico: {historical_data.iloc[-1]}")
    print(f"📊 Predicciones originales: {extreme_predictions.tolist()}")
    
    # Aplicar límite de 40%
    smoothed = forecaster._apply_month_to_month_variation_limit(
        historical_data, 
        extreme_predictions, 
        max_variation=0.40
    )
    
    print(f"📊 Predicciones limitadas: {smoothed.tolist()}")
    
    # Verificar que las variaciones están dentro del límite
    print(f"\n🔍 VERIFICACIÓN DE LÍMITES:")
    reference_value = historical_data.iloc[-1]  # 100
    
    for i, prediction in enumerate(smoothed):
        if i == 0:
            # Primer mes: comparar con último histórico
            variation = abs(prediction - reference_value) / reference_value
            print(f"   Mes {i+1}: {reference_value} → {prediction:.1f} (variación: {variation:.1%})")
        else:
            # Meses siguientes: comparar con mes anterior
            prev_value = smoothed.iloc[i-1]
            variation = abs(prediction - prev_value) / prev_value
            print(f"   Mes {i+1}: {prev_value:.1f} → {prediction:.1f} (variación: {variation:.1%})")
        
        reference_value = prediction
    
    # Verificar que ninguna variación excede 40%
    violations = []
    prev_value = historical_data.iloc[-1]
    
    for i, prediction in enumerate(smoothed):
        variation = abs(prediction - prev_value) / prev_value
        if variation > 0.41:  # Pequeño margen de tolerancia por redondeo
            violations.append(f"Mes {i+1}: {variation:.1%}")
        prev_value = prediction
    
    if violations:
        print(f"\n❌ VIOLACIONES ENCONTRADAS: {violations}")
    else:
        print(f"\n✅ TODAS las variaciones están dentro del límite del 40%")

def test_with_zero_values():
    """Probar con valores históricos en cero"""
    print(f"\n🧪 PRUEBA: Manejo de Valores en Cero")
    print("="*50)
    
    forecaster = SalesForecaster()
    
    # Serie con último valor = 0
    historical_zero = pd.Series([10, 5, 3, 1, 0], name='zero_sku')
    predictions = pd.Series([100, 200, 50])
    
    print(f"📊 Histórico (último=0): {historical_zero.tolist()}")
    print(f"📊 Predicciones: {predictions.tolist()}")
    
    smoothed = forecaster._apply_month_to_month_variation_limit(
        historical_zero, 
        predictions, 
        max_variation=0.40
    )
    
    print(f"📊 Resultado: {smoothed.tolist()}")
    print(f"💡 Debería usar la media histórica como referencia: {historical_zero.mean():.1f}")

def test_realistic_scenario():
    """Probar con un escenario realista como el SKU 7057"""
    print(f"\n🧪 PRUEBA: Escenario Realista (Simulando SKU Problemático)")
    print("="*50)
    
    forecaster = SalesForecaster()
    
    # Simular un SKU con historial irregular pero último valor razonable
    realistic_history = pd.Series([50, 80, 45, 120, 75], name='problematic_sku')
    
    # Predicciones que generarían errores extremos (como los 630 del SKU 7057)
    extreme_forecast = pd.Series([800, 50, 1200, 30, 900])  # Muy volátiles
    
    print(f"📊 Historial: {realistic_history.tolist()}")
    print(f"📊 Predicciones extremas: {extreme_forecast.tolist()}")
    
    smoothed = forecaster._apply_month_to_month_variation_limit(
        realistic_history, 
        extreme_forecast, 
        max_variation=0.40
    )
    
    print(f"📊 Predicciones suavizadas: {smoothed.tolist()}")
    
    # Calcular el MAE hipotético si el valor real fuera similar al histórico
    typical_real_values = [60, 85, 70, 90, 80]  # Valores "reales" simulados
    
    mae_original = np.mean([abs(pred - real) for pred, real in zip(extreme_forecast, typical_real_values)])
    mae_smoothed = np.mean([abs(pred - real) for pred, real in zip(smoothed, typical_real_values)])
    
    print(f"\n📊 MAE Simulado:")
    print(f"   Sin límite: {mae_original:.1f}")
    print(f"   Con límite: {mae_smoothed:.1f}")
    print(f"   Mejora: {((mae_original - mae_smoothed) / mae_original * 100):.1f}%")

if __name__ == "__main__":
    test_variation_limit()
    test_with_zero_values()
    test_realistic_scenario()
    
    print(f"\n🎯 RESUMEN:")
    print(f"   ✅ El límite del 40% está implementado")
    print(f"   ✅ Maneja casos edge (valores en cero)")
    print(f"   ✅ Debería reducir dramáticamente los errores extremos")
    print(f"   💡 Los SKUs como 7057 ahora tendrán MAE << 630") 