#!/usr/bin/env python3
"""
Script de diagnóstico rápido para Prophet
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# Configurar logging ANTES de importar Prophet
import logging
logging.getLogger('prophet').setLevel(logging.CRITICAL)
logging.getLogger('cmdstanpy').setLevel(logging.CRITICAL)

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    print("❌ Prophet no disponible")
    PROPHET_AVAILABLE = False

from sales_engine.forecaster.sales_forcaster import SalesForecaster

class ProphetDiagnostic:
    def __init__(self):
        self.forecaster = SalesForecaster()
        
    def test_prophet_diagnosis(self):
        """Diagnosticar Prophet para identificar problemas"""
        print("🔍 DIAGNÓSTICO PROPHET - ANÁLISIS GENERAL")
        print("="*60)
        
        # SOLO usar datos de la base de datos (NO CSV)
        print("📥 Obteniendo datos históricos de la BASE DE DATOS...")
        raw_historical_data = self.forecaster.get_historical_sales_data()
        
        if raw_historical_data is None:
            print("❌ No se pudo conectar a la base de datos")
            return
            
        print(f"✅ Datos obtenidos de BD: {len(raw_historical_data)} registros")
        
        # Preparar series temporales mensuales
        time_series_data = self.forecaster.prepare_monthly_time_series(raw_historical_data)
        
        print(f"📋 Columnas disponibles: {list(time_series_data.columns)}")
        print(f"📊 Shape de datos temporales: {time_series_data.shape}")
        
        # Buscar la columna correcta para SKU - puede ser diferente
        if 'sku' in time_series_data.columns:
            sku_column = 'sku'
        elif 'items_product_sku' in time_series_data.columns:
            sku_column = 'items_product_sku'
        elif 'product_sku' in time_series_data.columns:
            sku_column = 'product_sku'
        else:
            # Mostrar algunas muestras para entender la estructura
            print("🔍 Primeras 5 filas de datos temporales:")
            print(time_series_data.head())
            return
        
        # Verificar si SKU 5851 existe en datos originales
        raw_skus_5851 = raw_historical_data[raw_historical_data['items_product_sku'] == 5851]
        print(f"📊 SKU 5851 en datos originales: {len(raw_skus_5851)} registros")
        
        # Ver qué SKUs están disponibles en series temporales
        available_skus = time_series_data[sku_column].unique()
        print(f"📊 SKUs disponibles en series temporales: {len(available_skus)}")
        print(f"📊 Algunos SKUs ejemplo: {available_skus[:10]}")
        
        # Buscar SKUs que tengan datos recientes y suficiente historial
        print("\n🔍 Buscando SKUs con datos robustos para diagnóstico...")
        
        # Filtrar SKUs con datos hasta 2024 y al menos 36 meses de historial
        candidate_skus = []
        for sku in available_skus:
            sku_data_test = time_series_data[time_series_data[sku_column] == sku]
            
            # Verificar que tenga datos hasta al menos 2024
            latest_date = sku_data_test['month'].max()
            if pd.to_datetime(latest_date) < pd.to_datetime('2024-01-01'):
                continue
                
            # Verificar que tenga al menos 36 meses de datos
            if len(sku_data_test) < 36:
                continue
                
            # Verificar que tenga datos consistentes (no solo 0s)
            if sku_data_test['total_quantity'].sum() < 100:  # Al menos 100 unidades vendidas total
                continue
                
            candidate_skus.append((sku, len(sku_data_test), sku_data_test['month'].max(), sku_data_test['total_quantity'].sum()))
        
        print(f"🎯 SKUs candidatos encontrados: {len(candidate_skus)}")
        
        if not candidate_skus:
            print("❌ No se encontraron SKUs con datos suficientes")
            return
            
        # Ordenar por cantidad total de ventas (descendente) para usar el más activo
        candidate_skus.sort(key=lambda x: x[3], reverse=True)
        
        # Mostrar top 5 candidatos
        print("\n📊 TOP 5 SKUs candidatos:")
        for i, (sku, months, latest_date, total_sales) in enumerate(candidate_skus[:5]):
            print(f"   {i+1}. SKU {sku}: {months} meses, hasta {latest_date}, {total_sales:,.0f} unidades total")
        
        # Usar el SKU más activo
        target_sku, months, latest_date, total_sales = candidate_skus[0]
        sku_data = time_series_data[time_series_data[sku_column] == target_sku]
        
        print(f"\n✅ Seleccionado SKU {target_sku} para diagnóstico")
        print(f"   📊 {months} meses de datos, hasta {latest_date}")
        print(f"   🛒 {total_sales:,.0f} unidades vendidas en total")
            
        print(f"📊 Datos encontrados para SKU {target_sku}: {len(sku_data)} registros")
        print(f"📅 Período: {sku_data['month'].min()} a {sku_data['month'].max()}")
        
        # Mostrar últimos 12 meses
        print(f"\n📈 ÚLTIMOS 12 MESES (SKU {target_sku}):")
        last_12 = sku_data.tail(12)
        for _, row in last_12.iterrows():
            print(f"   {row['month']}: {row['total_quantity']}")
            
        # Para el diagnóstico, usar el último mes como "valor real" y entrenar con el resto
        last_month = sku_data['month'].max()
        real_value = sku_data[sku_data['month'] == last_month]['total_quantity'].iloc[0]
        
        print(f"\n🎯 DIAGNÓSTICO: Predecir {last_month} (valor real: {real_value})")
        print(f"   📊 Entrenaremos con datos hasta el mes anterior")
        
        # Usar todos los datos EXCEPTO el último mes para entrenar
        train_data = sku_data[sku_data['month'] < last_month].copy()
        test_month = last_month
        
        print(f"📊 Datos de entrenamiento: {len(train_data)} meses")
        print(f"📊 Último mes de entrenamiento: {train_data['month'].max()}")
        print(f"🎯 Mes a predecir: {test_month} (real: {real_value})")
        
        # Ejecutar diagnóstico Prophet
        diagnostic_result = self.forecast_prophet_diagnostic(train_data)
        
        if diagnostic_result:
            print(f"\n📊 RESULTADOS DIAGNÓSTICO PROPHET:")
            print(f"🎯 Valor real {test_month}: {real_value}")
            print("-" * 60)
            for config_name, result in diagnostic_result.items():
                error = abs(result['prediction'] - real_value) / real_value * 100
                status = "✅" if error < 20 else "⚠️" if error < 50 else "❌"
                print(f"   {status} {config_name}: {result['prediction']} (error: {error:.1f}%)")
                
            # Encontrar la mejor configuración
            best_config = min(diagnostic_result.items(), 
                            key=lambda x: abs(x[1]['prediction'] - real_value))
            best_error = abs(best_config[1]['prediction'] - real_value) / real_value * 100
            print(f"\n🏆 Mejor configuración: {best_config[0]} (error: {best_error:.1f}%)")
            
            if best_error > 50:
                print("\n💡 RECOMENDACIONES:")
                print("   - Prophet puede no ser adecuado para este tipo de datos")
                print("   - Considera usar modelos más simples (Linear, SARIMA)")
                print("   - Revisa si hay suficiente estacionalidad en los datos")
            elif best_error > 20:
                print("\n💡 RECOMENDACIONES:")
                print("   - Ajustar parámetros de Prophet")
                print("   - Considerar agregar regresores externos")
                print("   - Probar con seasonality_mode='multiplicative'")
            else:
                print("\n✅ Prophet funciona bien con esta configuración")
        
    def forecast_prophet_diagnostic(self, train_data: pd.DataFrame, steps: int = 1):
        """Prophet con diagnóstico completo"""
        if not PROPHET_AVAILABLE:
            return None
            
        try:
            # Preparar datos
            prophet_df = train_data[['month', 'total_quantity']].copy()
            prophet_df = prophet_df.rename(columns={'month': 'ds', 'total_quantity': 'y'})
            
            if len(prophet_df) < 2:
                return None
            
            prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
            
            print(f"\n🔍 DIAGNÓSTICO PROPHET:")
            print(f"   📊 Datos de entrada: {len(prophet_df)} puntos")
            print(f"   📊 Rango valores: {prophet_df['y'].min():.1f} - {prophet_df['y'].max():.1f}")
            print(f"   📊 Media: {prophet_df['y'].mean():.1f}, Mediana: {prophet_df['y'].median():.1f}")
            
            # Modelo Prophet con DIFERENTES configuraciones específicas para datos BD
            configs = [
                {
                    'name': 'Conservador Original',
                    'params': {
                        'yearly_seasonality': True,
                        'seasonality_mode': 'additive',
                        'changepoint_prior_scale': 0.05,
                        'seasonality_prior_scale': 10,
                    }
                },
                {
                    'name': 'Flexible Additive',
                    'params': {
                        'yearly_seasonality': True,
                        'seasonality_mode': 'additive',
                        'changepoint_prior_scale': 0.2,
                        'seasonality_prior_scale': 20,
                        'changepoint_range': 0.9,
                    }
                },
                {
                    'name': 'Multiplicativo Clásico',
                    'params': {
                        'yearly_seasonality': True,
                        'seasonality_mode': 'multiplicative',
                        'changepoint_prior_scale': 0.15,
                        'seasonality_prior_scale': 15,
                    }
                },
                {
                    'name': 'Solo Tendencia (Sin Estacionalidad)',
                    'params': {
                        'yearly_seasonality': False,
                        'seasonality_mode': 'additive',
                        'changepoint_prior_scale': 0.3,
                        'seasonality_prior_scale': 1,
                    }
                },
                {
                    'name': 'Híper Flexible',
                    'params': {
                        'yearly_seasonality': True,
                        'seasonality_mode': 'multiplicative',
                        'changepoint_prior_scale': 0.5,
                        'seasonality_prior_scale': 30,
                        'changepoint_range': 0.95,
                    }
                }
            ]
            
            results = {}
            
            for config in configs:
                print(f"\n🧪 Probando configuración: {config['name']}")
                
                model = Prophet(
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    mcmc_samples=0,
                    uncertainty_samples=100,  # Generar intervalos de confianza
                    **config['params']
                )
                
                # Agregar estacionalidad personalizada
                if len(prophet_df) >= 24:
                    model.add_seasonality(name='monthly', period=12, fourier_order=3)
                
                # Entrenar modelo
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(prophet_df)
                
                # Crear forecast
                last_date = prophet_df['ds'].max()
                next_date = last_date + pd.DateOffset(months=1)
                next_date = next_date + pd.offsets.MonthEnd(0)
                
                future = pd.DataFrame({'ds': prophet_df['ds'].tolist() + [next_date]})
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    forecast = model.predict(future)
                
                predicted_raw = forecast['yhat'].iloc[-1]
                
                # Intentar obtener intervalos de confianza si están disponibles
                try:
                    predicted_lower = forecast['yhat_lower'].iloc[-1]
                    predicted_upper = forecast['yhat_upper'].iloc[-1]
                    print(f"   🔮 Predicción: {predicted_raw:.1f} ({predicted_lower:.1f} - {predicted_upper:.1f})")
                except KeyError:
                    predicted_lower = predicted_raw
                    predicted_upper = predicted_raw
                    print(f"   🔮 Predicción: {predicted_raw:.1f} (sin intervalos de confianza)")
                
                results[config['name']] = {
                    'prediction': round(predicted_raw),
                    'lower': round(predicted_lower),
                    'upper': round(predicted_upper)
                }
            
            return results
                
        except Exception as e:
            print(f"❌ Error Prophet Diagnostic: {str(e)}")
            return None

if __name__ == "__main__":
    diagnostic = ProphetDiagnostic()
    diagnostic.test_prophet_diagnosis() 