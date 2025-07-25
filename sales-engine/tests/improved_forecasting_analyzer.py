#!/usr/bin/env python3
"""
Analizador de Forecasting Mejorado

Implementa técnicas avanzadas para reducir errores de predicción:
1. Ensemble de modelos
2. Detección de outliers
3. Feature engineering avanzado
4. Variables exógenas
5. Modelos más sofisticados
"""

import sys
import os
from datetime import date, datetime
from pathlib import Path
import pandas as pd
import numpy as np
import warnings
from typing import Dict, List, Optional, Tuple, Any
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import statsmodels.api as sm
from scipy import stats

# Suprimir warnings
warnings.filterwarnings('ignore')

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Imports internos
from sales_engine.forecaster.sales_forcaster import SalesForecaster

class ImprovedForecastingAnalyzer:
    """Analizador de forecasting con técnicas avanzadas para reducir errores."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.forecaster = SalesForecaster(use_test_odoo=use_test_odoo)
        self.target_skus = [5851, 6434, 5958]
        
        print("🚀 ImprovedForecastingAnalyzer inicializado")
        print(f"🎯 SKUs objetivo: {self.target_skus}")
        print("💡 Técnicas implementadas:")
        print("   - Ensemble de modelos")
        print("   - Detección de outliers") 
        print("   - Feature engineering avanzado")
        print("   - Modelos ML (Random Forest, Gradient Boosting)")
    
    def get_data(self) -> pd.DataFrame:
        """Obtener y preparar datos históricos."""
        print("\n📥 Obteniendo datos históricos...")
        
        # Intentar obtener datos usando el forecaster existente
        historical_data = self.forecaster.get_historical_sales_data()
        if historical_data is None:
            print("⚠️  No se pudo conectar a la base de datos. Intentando cargar ../data/historical_data.csv ...")
            csv_path = Path(__file__).parent.parent / "data" / "historical_data.csv"
            if not csv_path.exists():
                raise ValueError(f"No se pudieron obtener datos históricos ni encontrar el archivo {csv_path}")
            # Leer sin encabezado
            raw_df = pd.read_csv(csv_path, header=None)
            # Asignar nombres de columna (18 columnas)
            raw_df.columns = [
                'col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8', 'col9',
                'col10', 'col11', 'col12', 'product_name', 'sku', 'quantity', 'col16', 'issueddate', 'col18'
            ]
            # Extraer solo las columnas relevantes
            historical_data = raw_df[['issueddate', 'sku', 'quantity']].copy()
            historical_data.rename(columns={'sku': 'items_product_sku', 'quantity': 'items_quantity'}, inplace=True)
            historical_data['issueddate'] = pd.to_datetime(historical_data['issueddate'])
            # Asegurar tipos
            historical_data['items_product_sku'] = historical_data['items_product_sku'].astype(str)
            historical_data['items_quantity'] = pd.to_numeric(historical_data['items_quantity'], errors='coerce').fillna(0).astype(int)
            print(f"✅ Datos cargados desde CSV: {len(historical_data)} registros")
        
        # Preparar series temporales mensuales
        monthly_data = self.forecaster.prepare_monthly_time_series(historical_data)
        
        print(f"✅ Datos obtenidos: {len(monthly_data)} registros")
        print(f"📅 Período: {monthly_data['month'].min()} a {monthly_data['month'].max()}")
        print(f"📦 SKUs únicos: {monthly_data['sku'].nunique()}")
        
        return monthly_data
    
    def detect_outliers(self, ts_data: pd.Series, method='iqr') -> pd.Series:
        """Detectar y manejar outliers en series temporales."""
        if method == 'iqr':
            # Método IQR
            Q1 = ts_data.quantile(0.25)
            Q3 = ts_data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            # Identificar outliers
            outliers = (ts_data < lower_bound) | (ts_data > upper_bound)
            
        elif method == 'zscore':
            # Método Z-score
            z_scores = np.abs(stats.zscore(ts_data))
            outliers = z_scores > 3
        
        # Reemplazar outliers con mediana móvil
        cleaned_data = ts_data.copy()
        if outliers.any():
            print(f"   🔍 Detectados {outliers.sum()} outliers, aplicando corrección")
            # Usar mediana móvil de 3 períodos para reemplazar outliers
            rolling_median = ts_data.rolling(window=3, center=True).median()
            cleaned_data[outliers] = rolling_median[outliers]
            # Si no hay suficientes datos para rolling, usar mediana global
            cleaned_data[outliers & rolling_median.isna()] = ts_data.median()
        
        return cleaned_data
    
    def create_advanced_features(self, sku_data: pd.DataFrame) -> pd.DataFrame:
        """Crear features avanzados para mejorar predicciones."""
        df = sku_data.copy()
        df = df.sort_values('month').reset_index(drop=True)
        
        # Features temporales básicos
        df['year'] = df['month'].dt.year
        df['month_num'] = df['month'].dt.month
        df['quarter'] = df['month'].dt.quarter
        df['is_december'] = (df['month_num'] == 12).astype(int)  # Diciembre suele ser especial
        df['is_january'] = (df['month_num'] == 1).astype(int)    # Enero también
        
        # Features de tendencia
        df['time_index'] = range(len(df))
        df['time_squared'] = df['time_index'] ** 2  # Tendencia cuadrática
        
        # Features estacionales mejorados
        df['month_sin'] = np.sin(2 * np.pi * df['month_num'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month_num'] / 12)
        df['quarter_sin'] = np.sin(2 * np.pi * df['quarter'] / 4)
        df['quarter_cos'] = np.cos(2 * np.pi * df['quarter'] / 4)
        
        # Lags múltiples
        for lag in [1, 2, 3, 6, 12, 24]:
            if len(df) > lag:
                df[f'lag_{lag}'] = df['total_quantity'].shift(lag)
        
        # Rolling statistics
        for window in [3, 6, 12]:
            if len(df) >= window:
                df[f'rolling_mean_{window}'] = df['total_quantity'].rolling(window, min_periods=1).mean()
                df[f'rolling_std_{window}'] = df['total_quantity'].rolling(window, min_periods=1).std()
                df[f'rolling_max_{window}'] = df['total_quantity'].rolling(window, min_periods=1).max()
                df[f'rolling_min_{window}'] = df['total_quantity'].rolling(window, min_periods=1).min()
        
        # Features de crecimiento
        df['growth_1m'] = df['total_quantity'].pct_change(1).fillna(0)
        df['growth_3m'] = df['total_quantity'].pct_change(3).fillna(0)
        df['growth_12m'] = df['total_quantity'].pct_change(12).fillna(0)
        
        # Features de volatilidad
        df['volatility_3m'] = df['total_quantity'].rolling(3, min_periods=1).std().fillna(0)
        df['volatility_6m'] = df['total_quantity'].rolling(6, min_periods=1).std().fillna(0)
        
        # Features de ratio con respecto a promedios
        overall_mean = df['total_quantity'].mean()
        df['ratio_to_overall'] = df['total_quantity'] / max(overall_mean, 1)
        
        # Features de eventos especiales (COVID)
        covid_start = pd.Timestamp('2020-01-01')
        covid_end = pd.Timestamp('2023-06-30')
        df['covid_flag'] = 0
        mask = (df['month'] >= covid_start) & (df['month'] <= covid_end)
        df.loc[mask, 'covid_flag'] = 1
        
        # Features de recuperación post-COVID
        post_covid = df['month'] > covid_end
        df.loc[post_covid, 'post_covid_flag'] = 1
        df.loc[~post_covid, 'post_covid_flag'] = 0
        
        return df
    
    def forecast_ensemble(self, train_data: pd.DataFrame, target_month: int, target_year: int) -> Tuple[float, Dict[str, float]]:
        """Generar forecast usando ensemble de múltiples modelos."""
        predictions = {}
        weights = {}
        
        # 1. SARIMA (peso alto por ser ganador en backtesting)
        try:
            ts = train_data.set_index('month')['total_quantity'].asfreq('ME', fill_value=0)
            if len(ts) >= 24:
                model = sm.tsa.statespace.SARIMAX(
                    ts, order=(0, 1, 1), seasonal_order=(0, 1, 1, 12),
                    enforce_stationarity=True, enforce_invertibility=True
                )
                results = model.fit(disp=False, maxiter=50)
                if results.mle_retvals['converged']:
                    forecast = results.get_forecast(steps=1)
                    pred = max(0, forecast.predicted_mean.iloc[0])
                    predictions['sarima'] = pred
                    weights['sarima'] = 0.3  # Peso alto
        except:
            pass
        
        # 2. Random Forest con features avanzados
        try:
            df_features = self.create_advanced_features(train_data)
            df_clean = df_features.dropna()
            
            if len(df_clean) >= 12:
                # Seleccionar features relevantes
                feature_cols = [col for col in df_clean.columns if col not in 
                               ['month', 'sku', 'total_quantity'] and 'unnamed' not in col.lower()]
                
                X = df_clean[feature_cols]
                y = df_clean['total_quantity']
                
                # Entrenar Random Forest
                rf = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
                rf.fit(X, y)
                
                # Crear features para predicción
                last_row = df_clean.iloc[-1].copy()
                pred_features = last_row[feature_cols].copy()
                
                # Actualizar features para el mes objetivo
                pred_features['month_num'] = target_month
                pred_features['quarter'] = (target_month - 1) // 3 + 1
                pred_features['is_december'] = 1 if target_month == 12 else 0
                pred_features['is_january'] = 1 if target_month == 1 else 0
                pred_features['month_sin'] = np.sin(2 * np.pi * target_month / 12)
                pred_features['month_cos'] = np.cos(2 * np.pi * target_month / 12)
                pred_features['quarter_sin'] = np.sin(2 * np.pi * pred_features['quarter'] / 4)
                pred_features['quarter_cos'] = np.cos(2 * np.pi * pred_features['quarter'] / 4)
                pred_features['time_index'] += 1
                pred_features['time_squared'] = pred_features['time_index'] ** 2
                
                # Predicción
                pred = max(0, rf.predict([pred_features])[0])
                predictions['random_forest'] = pred
                weights['random_forest'] = 0.25
        except Exception as e:
            print(f"   ❌ Error Random Forest: {e}")
        
        # 3. Gradient Boosting
        try:
            df_features = self.create_advanced_features(train_data)
            df_clean = df_features.dropna()
            
            if len(df_clean) >= 12:
                feature_cols = [col for col in df_clean.columns if col not in 
                               ['month', 'sku', 'total_quantity'] and 'unnamed' not in col.lower()]
                
                X = df_clean[feature_cols]
                y = df_clean['total_quantity']
                
                # Entrenar Gradient Boosting
                gb = GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=6)
                gb.fit(X, y)
                
                # Crear features para predicción (similar a RF)
                last_row = df_clean.iloc[-1].copy()
                pred_features = last_row[feature_cols].copy()
                
                # Actualizar features
                pred_features['month_num'] = target_month
                pred_features['quarter'] = (target_month - 1) // 3 + 1
                pred_features['is_december'] = 1 if target_month == 12 else 0
                pred_features['is_january'] = 1 if target_month == 1 else 0
                pred_features['month_sin'] = np.sin(2 * np.pi * target_month / 12)
                pred_features['month_cos'] = np.cos(2 * np.pi * target_month / 12)
                pred_features['time_index'] += 1
                pred_features['time_squared'] = pred_features['time_index'] ** 2
                
                pred = max(0, gb.predict([pred_features])[0])
                predictions['gradient_boosting'] = pred
                weights['gradient_boosting'] = 0.25
        except Exception as e:
            print(f"   ❌ Error Gradient Boosting: {e}")
        
        # 4. Modelo lineal mejorado con features avanzados
        try:
            df_features = self.create_advanced_features(train_data)
            df_clean = df_features.dropna()
            
            if len(df_clean) >= 12:
                feature_cols = ['time_index', 'month_sin', 'month_cos', 'is_december', 'is_january']
                
                # Agregar lags disponibles
                for col in df_clean.columns:
                    if 'lag_' in col or 'rolling_mean_' in col:
                        feature_cols.append(col)
                
                available_cols = [col for col in feature_cols if col in df_clean.columns]
                
                X = df_clean[available_cols]
                y = df_clean['total_quantity']
                
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                
                model = LinearRegression()
                model.fit(X_scaled, y)
                
                # Predicción
                last_row = df_clean.iloc[-1].copy()
                pred_features = {}
                for col in available_cols:
                    if col == 'time_index':
                        pred_features[col] = last_row[col] + 1
                    elif col == 'month_sin':
                        pred_features[col] = np.sin(2 * np.pi * target_month / 12)
                    elif col == 'month_cos':
                        pred_features[col] = np.cos(2 * np.pi * target_month / 12)
                    elif col == 'is_december':
                        pred_features[col] = 1 if target_month == 12 else 0
                    elif col == 'is_january':
                        pred_features[col] = 1 if target_month == 1 else 0
                    else:
                        pred_features[col] = last_row[col]
                
                X_pred = np.array([[pred_features[col] for col in available_cols]])
                X_pred_scaled = scaler.transform(X_pred)
                
                pred = max(0, model.predict(X_pred_scaled)[0])
                predictions['linear_advanced'] = pred
                weights['linear_advanced'] = 0.2
        except Exception as e:
            print(f"   ❌ Error Linear avanzado: {e}")
        
        # Calcular ensemble weighted average
        if predictions:
            total_weight = sum(weights[model] for model in predictions.keys())
            if total_weight > 0:
                ensemble_pred = sum(predictions[model] * weights[model] for model in predictions.keys()) / total_weight
            else:
                ensemble_pred = np.mean(list(predictions.values()))
        else:
            ensemble_pred = None
            predictions = {'ensemble': None}
        
        return ensemble_pred, predictions
    
    def analyze_sku_patterns(self, sku_data: pd.DataFrame) -> Dict[str, Any]:
        """Analizar patrones específicos del SKU para mejor predicción."""
        patterns = {}
        
        # Detectar estacionalidad
        monthly_avg = sku_data.groupby(sku_data['month'].dt.month)['total_quantity'].mean()
        patterns['seasonality_strength'] = monthly_avg.std() / monthly_avg.mean() if monthly_avg.mean() > 0 else 0
        patterns['peak_months'] = monthly_avg.nlargest(3).index.tolist()
        patterns['low_months'] = monthly_avg.nsmallest(3).index.tolist()
        
        # Detectar tendencia
        time_corr = sku_data['total_quantity'].corr(pd.Series(range(len(sku_data))))
        patterns['trend_strength'] = abs(time_corr)
        patterns['trend_direction'] = 'up' if time_corr > 0.1 else 'down' if time_corr < -0.1 else 'stable'
        
        # Detectar volatilidad
        patterns['volatility'] = sku_data['total_quantity'].std() / sku_data['total_quantity'].mean() if sku_data['total_quantity'].mean() > 0 else 0
        
        # Detectar impacto COVID
        pre_covid = sku_data[sku_data['month'] < '2020-01-01']['total_quantity'].mean()
        covid_period = sku_data[(sku_data['month'] >= '2020-01-01') & (sku_data['month'] < '2023-07-01')]['total_quantity'].mean()
        post_covid = sku_data[sku_data['month'] >= '2023-07-01']['total_quantity'].mean()
        
        patterns['covid_impact'] = abs(covid_period - pre_covid) / pre_covid if pre_covid > 0 else 0
        patterns['recovery_ratio'] = post_covid / pre_covid if pre_covid > 0 else 1
        
        return patterns
    
    def adaptive_forecast(self, sku_data: pd.DataFrame, target_month: int, target_year: int) -> Tuple[float, str]:
        """Forecast adaptativo basado en patrones del SKU."""
        historical_data = sku_data[sku_data['month'] <= '2024-12-31'].copy()
        patterns = self.analyze_sku_patterns(historical_data)
        
        print(f"   📊 Patrones detectados:")
        print(f"      Estacionalidad: {patterns['seasonality_strength']:.2f}")
        print(f"      Tendencia: {patterns['trend_direction']} ({patterns['trend_strength']:.2f})")
        print(f"      Volatilidad: {patterns['volatility']:.2f}")
        print(f"      Impacto COVID: {patterns['covid_impact']:.2f}")
        
        # Elegir estrategia basada en patrones
        if patterns['seasonality_strength'] > 0.5:
            # Producto muy estacional - usar modelo que capture estacionalidad
            if target_month in patterns['peak_months']:
                print(f"   🎯 Estrategia: Estacional (mes pico)")
                adjustment = 1.2  # Incremento por mes pico
            elif target_month in patterns['low_months']:
                print(f"   🎯 Estrategia: Estacional (mes bajo)")
                adjustment = 0.8  # Reducción por mes bajo
            else:
                print(f"   🎯 Estrategia: Estacional (mes normal)")
                adjustment = 1.0
        elif patterns['trend_strength'] > 0.3:
            # Producto con tendencia fuerte
            print(f"   🎯 Estrategia: Tendencial ({patterns['trend_direction']})")
            adjustment = 1.1 if patterns['trend_direction'] == 'up' else 0.9
        else:
            # Producto estable
            print(f"   🎯 Estrategia: Estable")
            adjustment = 1.0
        
        # Generar ensemble forecast
        ensemble_pred, individual_preds = self.forecast_ensemble(historical_data, target_month, target_year)
        
        if ensemble_pred is not None:
            # Aplicar ajuste adaptativo
            adaptive_pred = ensemble_pred * adjustment
            
            # Aplicar límites basados en patrones históricos
            recent_avg = historical_data.tail(6)['total_quantity'].mean()
            max_reasonable = recent_avg * 3
            min_reasonable = max(0, recent_avg * 0.3)
            
            adaptive_pred = max(min_reasonable, min(adaptive_pred, max_reasonable))
            
            strategy = f"Ensemble adaptativo (ajuste: {adjustment:.1f}x)"
        else:
            # Fallback a promedio de últimos meses con estacionalidad
            recent_data = historical_data.tail(12)
            same_month_data = historical_data[historical_data['month'].dt.month == target_month]
            
            if len(same_month_data) > 0:
                adaptive_pred = same_month_data['total_quantity'].mean() * adjustment
                strategy = f"Promedio estacional (ajuste: {adjustment:.1f}x)"
            else:
                adaptive_pred = recent_data['total_quantity'].mean() * adjustment
                strategy = f"Promedio reciente (ajuste: {adjustment:.1f}x)"
        
        return round(adaptive_pred), strategy
    
    def analyze_specific_skus_improved(self, data: pd.DataFrame) -> None:
        """Análisis mejorado para SKUs específicos."""
        print("\n" + "="*80)
        print("🚀 ANÁLISIS MEJORADO: ENERO 2025 - SKUs 5851, 6434, 5958")
        print("="*80)
        
        with self.forecaster:
            for sku in self.target_skus:
                print(f"\n📦 SKU {sku}:")
                print("-" * 70)
                
                # Obtener datos del SKU
                sku_data = data[data['sku'] == str(sku)].copy()
                if sku_data.empty:
                    print(f"   ❌ SKU {sku} no encontrado en el dataset")
                    continue
                
                sku_data = sku_data.sort_values('month')
                
                # Datos históricos hasta diciembre 2024
                historical_data = sku_data[sku_data['month'] <= '2024-12-31'].copy()
                
                # Verificar valor real de enero 2025
                january_2025_data = sku_data[sku_data['month'] == '2025-01-31']
                actual_value = None
                if not january_2025_data.empty:
                    actual_value = january_2025_data['total_quantity'].iloc[0]
                
                if len(historical_data) < 24:
                    print(f"   ❌ Datos insuficientes: {len(historical_data)} meses")
                    continue
                
                print(f"   📊 Datos históricos: {len(historical_data)} meses")
                print(f"   📊 Valor real enero 2025: {actual_value if actual_value is not None else 'No disponible'}")
                
                # Limpiar outliers
                print(f"   🧹 Limpiando outliers...")
                historical_data['total_quantity'] = self.detect_outliers(historical_data['total_quantity'])
                
                # Forecast adaptativo mejorado
                print(f"\n   🔮 FORECAST ADAPTATIVO PARA ENERO 2025:")
                
                pred_adaptive, strategy = self.adaptive_forecast(historical_data, 1, 2025)
                
                if actual_value is not None:
                    error_pct = ((pred_adaptive - actual_value) / actual_value) * 100
                    status = "✅ Excelente" if abs(error_pct) < 10 else "✅ Bueno" if abs(error_pct) < 20 else "⚠️ Regular" if abs(error_pct) < 40 else "❌ Malo"
                    
                    print(f"\n   📊 RESULTADOS:")
                    print(f"   {'Método':<30} {'Predicción':<12} {'Real':<8} {'Error %':<10} {'Estado'}")
                    print("   " + "-" * 70)
                    print(f"   {'Forecast Adaptativo':<30} {pred_adaptive:<12.0f} {actual_value:<8} {error_pct:<10.1f}% {status}")
                    print(f"   Estrategia utilizada: {strategy}")
                    
                    # Comparar con método anterior (mejor del análisis básico)
                    if sku == 5851:
                        old_pred, old_error = 131, -38.2
                        improvement = abs(old_error) - abs(error_pct)
                    elif sku == 6434:
                        old_pred, old_error = 17, -26.1
                        improvement = abs(old_error) - abs(error_pct)
                    elif sku == 5958:
                        old_pred, old_error = 86, 3.6
                        improvement = abs(old_error) - abs(error_pct)
                    
                    print(f"   {'Método Anterior (mejor)':<30} {old_pred:<12.0f} {actual_value:<8} {old_error:<10.1f}% {'✅' if abs(old_error) < 20 else '⚠️' if abs(old_error) < 40 else '❌'}")
                    
                    if improvement > 0:
                        print(f"\n   🎉 ¡MEJORA! Reducción de error: {improvement:.1f} puntos porcentuales")
                    else:
                        print(f"\n   📉 Sin mejora: {-improvement:.1f} puntos porcentuales peor")
                else:
                    print(f"\n   📊 PREDICCIÓN: {pred_adaptive:.0f} unidades")
                    print(f"   Estrategia: {strategy}")
    
    def run_analysis(self) -> None:
        """Ejecutar análisis completo mejorado."""
        print("🚀 ANÁLISIS DE FORECASTING MEJORADO PARA ENERO 2025")
        print("=" * 70)
        print("SKUs objetivo: 5851, 6434, 5958")
        print("Objetivo: Reducir errores de predicción")
        print("=" * 70)
        
        try:
            # Obtener datos
            data = self.get_data()
            
            # Verificar que los SKUs existen
            available_skus = data['sku'].unique()
            missing_skus = [str(sku) for sku in self.target_skus if str(sku) not in available_skus]
            
            if missing_skus:
                print(f"⚠️  SKUs no encontrados: {missing_skus}")
                print(f"📋 SKUs disponibles: {list(available_skus)[:10]}...")
            
            # Ejecutar análisis mejorado
            self.analyze_specific_skus_improved(data)
            
            print(f"\n" + "="*70)
            print("✅ ANÁLISIS MEJORADO COMPLETADO")
            print("="*70)
            print("\n💡 TÉCNICAS IMPLEMENTADAS PARA REDUCIR ERRORES:")
            print("   1. ✅ Ensemble de múltiples modelos (SARIMA + RF + GB + Linear)")
            print("   2. ✅ Detección y corrección de outliers")
            print("   3. ✅ Feature engineering avanzado (lags, rolling stats, estacionalidad)")
            print("   4. ✅ Forecasting adaptativo basado en patrones del producto")
            print("   5. ✅ Límites inteligentes basados en datos históricos")
            
        except Exception as e:
            print(f"\n❌ Error durante análisis: {str(e)}")
            import traceback
            traceback.print_exc()
            return 1
        
        return 0


def main():
    """Función principal."""
    try:
        analyzer = ImprovedForecastingAnalyzer()
        exit_code = analyzer.run_analysis()
        return exit_code
        
    except Exception as e:
        print(f"\n❌ Error durante ejecución: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 