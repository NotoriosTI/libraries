#!/usr/bin/env python3
"""
Análisis Específico de Forecasts para Enero 2025

Genera forecasts para los SKUs 5851, 6434, 5958 en enero 2025
usando todos los modelos disponibles y compara con valores reales.
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
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import statsmodels.api as sm

# Suprimir warnings de statsmodels
warnings.filterwarnings('ignore')

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Imports internos
from sales_engine.forecaster.sales_forcaster import SalesForecaster

# Agregar imports para el modelo mejorado
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from scipy import stats

class January2025Analyzer:
    """Analizador específico para forecasts de enero 2025."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.forecaster = SalesForecaster(use_test_odoo=use_test_odoo)
        self.target_skus = [5851, 6434, 5958]
        
        print("🔍 January2025Analyzer inicializado")
        print(f"🎯 SKUs objetivo: {self.target_skus}")
    
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
    
    def add_covid_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega la variable exógena covid_flag=1 entre 2020-01 y 2023-06, 0 en el resto."""
        df = df.copy()
        df['covid_flag'] = 0
        covid_start = pd.Timestamp('2020-01-01')
        covid_end = pd.Timestamp('2023-06-30')
        mask = (df['month'] >= covid_start) & (df['month'] <= covid_end)
        df.loc[mask, 'covid_flag'] = 1
        return df
    
    def forecast_sarima_all_months(self, train_data: pd.DataFrame, steps: int = 1) -> Optional[pd.Series]:
        """SARIMA usando todos los meses."""
        try:
            # Crear serie temporal completa
            ts = train_data.set_index('month')['total_quantity'].asfreq('ME', fill_value=0)
            
            if len(ts) < 24:
                return None
            
            # Modelo SARIMA
            model = sm.tsa.statespace.SARIMAX(
                ts,
                order=(0, 1, 1),
                seasonal_order=(0, 1, 1, 12),
                enforce_stationarity=True,
                enforce_invertibility=True
            )
            
            results = model.fit(disp=False, maxiter=50)
            
            if not results.mle_retvals['converged']:
                return None
            
            forecast = results.get_forecast(steps=steps)
            predicted_values = forecast.predicted_mean
            
            # Aplicar límites razonables
            historical_max = ts.max()
            upper_limit = max(historical_max * 2, 50)
            predicted_values = predicted_values.clip(lower=0, upper=upper_limit)
            
            return predicted_values.round().astype(int)
            
        except Exception as e:
            print(f"    ❌ Error SARIMA todos los meses: {str(e)}")
            return None
    
    def forecast_sarima_same_month(self, train_data: pd.DataFrame, target_month: int) -> Optional[float]:
        """SARIMA usando solo el mismo mes histórico."""
        try:
            # Filtrar solo el mes objetivo
            same_month_data = train_data[train_data['month'].dt.month == target_month].copy()
            same_month_data = same_month_data.sort_values('month')
            
            if len(same_month_data) < 5:  # Necesitamos al menos 5 años
                return None
            
            # Crear serie anual del mismo mes
            ts = same_month_data.set_index('month')['total_quantity']
            
            # Modelo ARIMA simple (sin estacionalidad porque solo es un mes)
            model = sm.tsa.statespace.SARIMAX(
                ts,
                order=(1, 1, 1),
                enforce_stationarity=True,
                enforce_invertibility=True
            )
            
            results = model.fit(disp=False, maxiter=50)
            
            if not results.mle_retvals['converged']:
                return None
            
            forecast = results.get_forecast(steps=1)
            predicted_value = forecast.predicted_mean.iloc[0]
            
            # Aplicar límites
            historical_max = ts.max()
            upper_limit = max(historical_max * 2, 5)
            predicted_value = max(0, min(predicted_value, upper_limit))
            
            return round(predicted_value)
            
        except Exception as e:
            print(f"    ❌ Error SARIMA mismo mes: {str(e)}")
            return None
    
    def forecast_sarimax_all_months(self, train_data: pd.DataFrame, steps: int = 1) -> Optional[pd.Series]:
        """SARIMAX usando todos los meses y covid_flag como exógena."""
        try:
            ts = train_data.set_index('month')['total_quantity'].asfreq('ME', fill_value=0)
            exog = train_data.set_index('month')['covid_flag'].asfreq('ME', fill_value=0)
            if len(ts) < 24:
                return None
            model = sm.tsa.statespace.SARIMAX(
                ts,
                exog=exog,
                order=(0, 1, 1),
                seasonal_order=(0, 1, 1, 12),
                enforce_stationarity=True,
                enforce_invertibility=True
            )
            results = model.fit(disp=False, maxiter=50)
            if not results.mle_retvals['converged']:
                return None
            # Exógena futura: 0 si se asume sin covid
            exog_future = pd.Series([0]*steps, index=pd.date_range(ts.index[-1]+pd.offsets.MonthEnd(1), periods=steps, freq='M'))
            forecast = results.get_forecast(steps=steps, exog=exog_future)
            predicted_values = forecast.predicted_mean
            historical_max = ts.max()
            upper_limit = max(historical_max * 2, 50)
            predicted_values = predicted_values.clip(lower=0, upper=upper_limit)
            return predicted_values.round().astype(int)
        except Exception as e:
            print(f"    ❌ Error SARIMAX todos los meses: {str(e)}")
            return None

    def forecast_sarimax_same_month(self, train_data: pd.DataFrame, target_month: int) -> Optional[float]:
        """SARIMAX usando solo el mismo mes histórico y covid_flag como exógena."""
        try:
            same_month_data = train_data[train_data['month'].dt.month == target_month].copy()
            same_month_data = same_month_data.sort_values('month')
            if len(same_month_data) < 5:
                return None
            ts = same_month_data.set_index('month')['total_quantity']
            exog = same_month_data.set_index('month')['covid_flag']
            model = sm.tsa.statespace.SARIMAX(
                ts,
                exog=exog,
                order=(1, 1, 1),
                enforce_stationarity=True,
                enforce_invertibility=True
            )
            results = model.fit(disp=False, maxiter=50)
            if not results.mle_retvals['converged']:
                return None
            exog_future = pd.Series([0], index=[ts.index[-1] + pd.offsets.MonthEnd(1)])
            forecast = results.get_forecast(steps=1, exog=exog_future)
            predicted_value = forecast.predicted_mean.iloc[0]
            historical_max = ts.max()
            upper_limit = max(historical_max * 2, 5)
            predicted_value = max(0, min(predicted_value, upper_limit))
            return round(predicted_value)
        except Exception as e:
            print(f"    ❌ Error SARIMAX mismo mes: {str(e)}")
            return None
    
    def create_features_all_months(self, ts_data: pd.DataFrame) -> pd.DataFrame:
        """Crear features para regresión lineal usando todos los meses."""
        df = ts_data.copy()
        df = df.sort_values('month').reset_index(drop=True)
        
        # Features temporales
        df['year'] = df['month'].dt.year
        df['month_num'] = df['month'].dt.month
        df['quarter'] = df['month'].dt.quarter
        
        # Features de tendencia
        df['time_index'] = range(len(df))
        
        # Features estacionales
        df['month_sin'] = np.sin(2 * np.pi * df['month_num'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month_num'] / 12)
        
        # Lags
        if len(df) >= 13:
            df['lag_12'] = df['total_quantity'].shift(12)
        if len(df) >= 25:
            df['lag_24'] = df['total_quantity'].shift(24)
        
        # Rolling means
        if len(df) >= 6:
            df['rolling_6m'] = df['total_quantity'].rolling(6, min_periods=3).mean()
        if len(df) >= 12:
            df['rolling_12m'] = df['total_quantity'].rolling(12, min_periods=6).mean()
        
        return df
    
    def forecast_linear_all_months(self, train_data: pd.DataFrame, target_month: int, target_year: int) -> Optional[float]:
        """Regresión lineal usando todos los meses."""
        try:
            # Crear features
            df_features = self.create_features_all_months(train_data)
            
            # Remover filas con NaN
            df_clean = df_features.dropna()
            
            if len(df_clean) < 12:
                return None
            
            # Preparar datos
            feature_cols = ['time_index', 'month_num', 'quarter', 'month_sin', 'month_cos']
            if 'lag_12' in df_clean.columns:
                feature_cols.append('lag_12')
            if 'lag_24' in df_clean.columns:
                feature_cols.append('lag_24')
            if 'rolling_6m' in df_clean.columns:
                feature_cols.append('rolling_6m')
            if 'rolling_12m' in df_clean.columns:
                feature_cols.append('rolling_12m')
            
            available_cols = [col for col in feature_cols if col in df_clean.columns]
            
            X = df_clean[available_cols]
            y = df_clean['total_quantity']
            
            # Entrenar modelo
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            model = LinearRegression()
            model.fit(X_scaled, y)
            
            # Crear features para predicción
            last_row = df_clean.iloc[-1].copy()
            next_time_index = last_row['time_index'] + 1
            
            # Estimar lag_12
            lag_12_value = 0
            if target_month <= 12:
                same_month_prev = df_clean[df_clean['month_num'] == target_month]
                if len(same_month_prev) > 0:
                    lag_12_value = same_month_prev['total_quantity'].iloc[-1]
            
            pred_features = {
                'time_index': next_time_index,
                'month_num': target_month,
                'quarter': (target_month - 1) // 3 + 1,
                'month_sin': np.sin(2 * np.pi * target_month / 12),
                'month_cos': np.cos(2 * np.pi * target_month / 12),
            }
            
            if 'lag_12' in available_cols:
                pred_features['lag_12'] = lag_12_value
            if 'lag_24' in available_cols:
                pred_features['lag_24'] = 0
            if 'rolling_6m' in available_cols:
                pred_features['rolling_6m'] = df_clean['total_quantity'].tail(6).mean()
            if 'rolling_12m' in available_cols:
                pred_features['rolling_12m'] = df_clean['total_quantity'].tail(12).mean()
            
            # Crear vector de predicción
            X_pred = np.array([[pred_features[col] for col in available_cols]])
            X_pred_scaled = scaler.transform(X_pred)
            
            prediction = model.predict(X_pred_scaled)[0]
            
            # Aplicar límites
            historical_max = y.max()
            upper_limit = max(historical_max * 2, 5)
            prediction = max(0, min(prediction, upper_limit))
            
            return round(prediction)
            
        except Exception as e:
            print(f"    ❌ Error Linear todos los meses: {str(e)}")
            return None
    
    def create_features_same_month(self, ts_data: pd.DataFrame, target_month: int) -> pd.DataFrame:
        """Crear features para regresión lineal usando solo el mismo mes."""
        df = ts_data.copy()
        
        # Filtrar solo el mes objetivo
        df = df[df['month'].dt.month == target_month].copy()
        df = df.sort_values('month').reset_index(drop=True)
        
        if len(df) < 3:
            return pd.DataFrame()
        
        # Features simples para mismo mes
        df['year'] = df['month'].dt.year
        df['time_index'] = range(len(df))
        
        # Lag del año anterior
        if len(df) >= 2:
            df['lag_1y'] = df['total_quantity'].shift(1)
        if len(df) >= 3:
            df['lag_2y'] = df['total_quantity'].shift(2)
        
        return df
    
    def forecast_linear_same_month(self, train_data: pd.DataFrame, target_month: int, target_year: int) -> Optional[float]:
        """Regresión lineal usando solo el mismo mes."""
        try:
            # Crear features para mismo mes
            df_features = self.create_features_same_month(train_data, target_month)
            
            if df_features.empty or len(df_features) < 3:
                return None
            
            # Remover filas con NaN
            df_clean = df_features.dropna()
            
            if len(df_clean) < 3:
                return None
            
            # Preparar datos
            feature_cols = ['time_index']
            if 'lag_1y' in df_clean.columns:
                feature_cols.append('lag_1y')
            if 'lag_2y' in df_clean.columns:
                feature_cols.append('lag_2y')
            
            available_cols = [col for col in feature_cols if col in df_clean.columns]
            
            X = df_clean[available_cols]
            y = df_clean['total_quantity']
            
            # Entrenar modelo
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            model = LinearRegression()
            model.fit(X_scaled, y)
            
            # Predicción para el año objetivo
            next_time_index = len(df_clean)
            
            pred_features = {'time_index': next_time_index}
            
            if 'lag_1y' in available_cols and len(df_clean) > 0:
                pred_features['lag_1y'] = df_clean['total_quantity'].iloc[-1]
            if 'lag_2y' in available_cols and len(df_clean) > 1:
                pred_features['lag_2y'] = df_clean['total_quantity'].iloc[-2]
            
            X_pred = np.array([[pred_features[col] for col in available_cols]])
            X_pred_scaled = scaler.transform(X_pred)
            
            prediction = model.predict(X_pred_scaled)[0]
            
            # Aplicar límites
            historical_max = y.max()
            upper_limit = max(historical_max * 2, 5)
            prediction = max(0, min(prediction, upper_limit))
            
            return round(prediction)
            
        except Exception as e:
            print(f"    ❌ Error Linear mismo mes: {str(e)}")
            return None
    
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
    
    def adaptive_forecast(self, sku_data: pd.DataFrame, target_month: int, target_year: int, verbose: bool = True) -> Tuple[float, str]:
        """Forecast adaptativo basado en patrones del SKU."""
        historical_data = sku_data[sku_data['month'] <= '2024-12-31'].copy()
        patterns = self.analyze_sku_patterns(historical_data)
        
        if verbose:
            print(f"   📊 Patrones detectados:")
            print(f"      Estacionalidad: {patterns['seasonality_strength']:.2f}")
            print(f"      Tendencia: {patterns['trend_direction']} ({patterns['trend_strength']:.2f})")
            print(f"      Volatilidad: {patterns['volatility']:.2f}")
            print(f"      Impacto COVID: {patterns['covid_impact']:.2f}")
        
        # Elegir estrategia basada en patrones
        if patterns['seasonality_strength'] > 0.5:
            # Producto muy estacional - usar modelo que capture estacionalidad
            if target_month in patterns['peak_months']:
                strategy_desc = "Estacional (mes pico)"
                adjustment = 1.2  # Incremento por mes pico
            elif target_month in patterns['low_months']:
                strategy_desc = "Estacional (mes bajo)"
                adjustment = 0.8  # Reducción por mes bajo
            else:
                strategy_desc = "Estacional (mes normal)"
                adjustment = 1.0
        elif patterns['trend_strength'] > 0.3:
            # Producto con tendencia fuerte
            strategy_desc = f"Tendencial ({patterns['trend_direction']})"
            adjustment = 1.1 if patterns['trend_direction'] == 'up' else 0.9
        else:
            # Producto estable
            strategy_desc = "Estable"
            adjustment = 1.0
        
        if verbose:
            print(f"   🎯 Estrategia: {strategy_desc}")
        
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
            
            strategy = f"Ensemble {strategy_desc} (ajuste: {adjustment:.1f}x)"
        else:
            # Fallback a promedio de últimos meses con estacionalidad
            recent_data = historical_data.tail(12)
            same_month_data = historical_data[historical_data['month'].dt.month == target_month]
            
            if len(same_month_data) > 0:
                adaptive_pred = same_month_data['total_quantity'].mean() * adjustment
                strategy = f"Promedio {strategy_desc} (ajuste: {adjustment:.1f}x)"
            else:
                adaptive_pred = recent_data['total_quantity'].mean() * adjustment
                strategy = f"Promedio {strategy_desc} (ajuste: {adjustment:.1f}x)"
        
        return round(adaptive_pred), strategy
    
    def _print_forecast_row(self, model_name: str, prediction: float, actual: float) -> None:
        """Helper para imprimir una fila del forecast."""
        if prediction is None:
            print(f"   {model_name:<25} {'N/A':<12} {actual if actual is not None else 'N/A':<8} {'N/A':<10} ❌ Falló")
        else:
            if actual is not None:
                if actual != 0:
                    error_pct = ((prediction - actual) / actual) * 100
                    status = "✅" if abs(error_pct) < 20 else "⚠️" if abs(error_pct) < 50 else "❌"
                    print(f"   {model_name:<25} {prediction:<12.0f} {actual:<8} {error_pct:<10.1f}% {status}")
                else:
                    error_pct = float('inf') if prediction != 0 else 0
                    print(f"   {model_name:<25} {prediction:<12.0f} {actual:<8} {'∞' if error_pct == float('inf') else '0':<10} ⚠️")
            else:
                print(f"   {model_name:<25} {prediction:<12.0f} {'N/A':<8} {'N/A':<10} ⚠️")
    
    def analyze_specific_skus_january_2025(self, data: pd.DataFrame) -> None:
        """Análisis específico para SKUs 5851, 6434, 5958 en enero 2025."""
        print("\n" + "="*80)
        print("📅 ANÁLISIS ESPECÍFICO: ENERO 2025 - SKUs 5851, 6434, 5958")
        print("="*80)
        
        with self.forecaster:
            for sku in self.target_skus:
                print(f"\n📦 SKU {sku}:")
                print("-" * 60)
                
                # Obtener datos del SKU
                sku_data = data[data['sku'] == str(sku)].copy()
                if sku_data.empty:
                    print(f"   ❌ SKU {sku} no encontrado en el dataset")
                    continue
                
                sku_data = sku_data.sort_values('month')
                sku_data = self.add_covid_flag(sku_data)
                
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
                
                # Limpiar outliers ANTES de generar forecasts
                print(f"   🧹 Limpiando outliers...")
                historical_data['total_quantity'] = self.detect_outliers(historical_data['total_quantity'])
                
                # Generar forecasts
                print(f"\n   🔮 FORECASTS PARA ENERO 2025:")
                print(f"   {'Modelo':<25} {'Predicción':<12} {'Real':<8} {'Error %':<10} {'Estado'}")
                print("   " + "-" * 65)
                
                # 1. SARIMA (todos los meses)
                try:
                    sarima_forecast = self.forecast_sarima_all_months(historical_data, 1)
                    pred_sarima = sarima_forecast.iloc[0] if sarima_forecast is not None else None
                except:
                    pred_sarima = None
                
                self._print_forecast_row("SARIMA (todos meses)", pred_sarima, actual_value)
                
                # 2. SARIMA (mismo mes)
                try:
                    pred_sarima_same = self.forecast_sarima_same_month(historical_data, 1)
                except:
                    pred_sarima_same = None
                
                self._print_forecast_row("SARIMA (enero)", pred_sarima_same, actual_value)
                
                # 3. Linear (todos los meses)
                try:
                    pred_linear = self.forecast_linear_all_months(historical_data, 1, 2025)
                except:
                    pred_linear = None
                
                self._print_forecast_row("Linear (todos meses)", pred_linear, actual_value)
                
                # 4. Linear (mismo mes)
                try:
                    pred_linear_same = self.forecast_linear_same_month(historical_data, 1, 2025)
                except:
                    pred_linear_same = None
                
                self._print_forecast_row("Linear (enero)", pred_linear_same, actual_value)
                
                # 5. SARIMAX (todos los meses)
                try:
                    sarimax_forecast = self.forecast_sarimax_all_months(historical_data, 1)
                    pred_sarimax = sarimax_forecast.iloc[0] if sarimax_forecast is not None else None
                except:
                    pred_sarimax = None
                
                self._print_forecast_row("SARIMAX (todos meses)", pred_sarimax, actual_value)
                
                # 6. SARIMAX (mismo mes)
                try:
                    pred_sarimax_same = self.forecast_sarimax_same_month(historical_data, 1)
                except:
                    pred_sarimax_same = None
                
                self._print_forecast_row("SARIMAX (enero)", pred_sarimax_same, actual_value)
                
                # 7. Forecaster productivo
                try:
                    ts_data = historical_data.set_index('month')['total_quantity']
                    prod_forecast = self.forecaster._forecast_single_sku(ts_data, steps=1)
                    pred_productivo = prod_forecast.iloc[0] if prod_forecast is not None else None
                except Exception as e:
                    print(f"   ⚠️  Error en forecaster productivo: {e}")
                    pred_productivo = None
                
                self._print_forecast_row("Productivo", pred_productivo, actual_value)
                
                # 8. Ensemble Adaptativo (Modelo Mejorado)
                try:
                    pred_adaptive, strategy = self.adaptive_forecast(sku_data, 1, 2025, verbose=False)
                except Exception as e:
                    print(f"   ❌ Error en modelo adaptativo: {e}")
                    pred_adaptive = None
                    strategy = "Error"
                
                self._print_forecast_row("🚀 Ensemble Adaptativo", pred_adaptive, actual_value)
                
                # Resumen para este SKU con COMPARACIÓN DE MEJORAS
                if actual_value is not None:
                    forecasts = [
                        ("SARIMA (todos)", pred_sarima),
                        ("SARIMA (enero)", pred_sarima_same),
                        ("Linear (todos)", pred_linear),
                        ("Linear (enero)", pred_linear_same),
                        ("SARIMAX (todos)", pred_sarimax),
                        ("SARIMAX (enero)", pred_sarimax_same),
                        ("Productivo", pred_productivo),
                        ("🚀 Ensemble Adaptativo", pred_adaptive)
                    ]
                    
                    valid_forecasts = [(name, pred) for name, pred in forecasts if pred is not None]
                    if valid_forecasts:
                        errors = [(name, abs((pred - actual_value) / actual_value * 100)) 
                                for name, pred in valid_forecasts if actual_value != 0]
                        if errors:
                            best_model = min(errors, key=lambda x: x[1])
                            print(f"\n   🏆 MEJOR MODELO GENERAL: {best_model[0]} (error: {best_model[1]:.1f}%)")
                            
                            # Mostrar comparación específica con modelo mejorado
                            if pred_adaptive is not None:
                                adaptive_error = abs((pred_adaptive - actual_value) / actual_value * 100)
                                
                                # Encontrar el mejor modelo anterior (excluyendo adaptativo)
                                previous_errors = [(name, error) for name, error in errors if "Ensemble" not in name]
                                if previous_errors:
                                    best_previous = min(previous_errors, key=lambda x: x[1])
                                    improvement = best_previous[1] - adaptive_error
                                    
                                    print(f"\n   📊 COMPARACIÓN DE MEJORAS:")
                                    print(f"      Mejor modelo anterior: {best_previous[0]} ({best_previous[1]:.1f}% error)")
                                    print(f"      🚀 Modelo mejorado:     Ensemble Adaptativo ({adaptive_error:.1f}% error)")
                                    
                                    if improvement > 0:
                                        print(f"      🎉 ¡MEJORA!: -{improvement:.1f} puntos porcentuales")
                                        print(f"      📈 Reducción de error: {improvement/best_previous[1]*100:.1f}%")
                                    else:
                                        print(f"      📉 Sin mejora: +{abs(improvement):.1f} puntos porcentuales")
                                            
                                    # Clasificar la mejora
                                    if improvement > 10:
                                        print(f"      🌟 EXCELENTE mejora!")
                                    elif improvement > 5:
                                        print(f"      ✅ BUENA mejora!")
                                    elif improvement > 0:
                                        print(f"      ⚠️ Mejora menor")
                                    else:
                                        print(f"      ❌ Necesita más trabajo")
                
                # Mostrar detalles del modelo mejorado al final
                if pred_adaptive is not None:
                    print(f"\n   🔍 DETALLES DEL MODELO ENSEMBLE ADAPTATIVO:")
                    # Ejecutar análisis detallado para mostrar patrones
                    try:
                        _, detailed_strategy = self.adaptive_forecast(sku_data, 1, 2025, verbose=True)
                    except:
                        print(f"      Estrategia utilizada: {strategy}")
                else:
                    print(f"\n   ❌ Modelo Ensemble Adaptativo falló para este SKU") 
    
    def run_analysis(self) -> None:
        """Ejecutar análisis completo."""
        print("🔍 ANÁLISIS DE FORECASTS PARA ENERO 2025 - MEJORADO")
        print("=" * 70)
        print("SKUs objetivo: 5851, 6434, 5958")
        print("🚀 Incluye modelo ensemble adaptativo mejorado")
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
            
            # Ejecutar análisis específico
            self.analyze_specific_skus_january_2025(data)
            
            print(f"\n" + "="*70)
            print("✅ ANÁLISIS MEJORADO COMPLETADO")
            print("="*70)
            print("\n💡 TÉCNICAS DE MEJORA IMPLEMENTADAS:")
            print("   🧹 Detección y corrección de outliers")
            print("   🎯 Ensemble de 4 modelos (SARIMA + RF + GB + Linear)")
            print("   📊 Análisis adaptativo de patrones por SKU")
            print("   ⚙️ Feature engineering avanzado (+20 features)")
            print("   🎛️ Ajustes automáticos por estacionalidad/tendencia")
            
        except Exception as e:
            print(f"\n❌ Error durante análisis: {str(e)}")
            import traceback
            traceback.print_exc()
            return 1
        
        return 0


def main():
    """Función principal."""
    try:
        analyzer = January2025Analyzer()
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