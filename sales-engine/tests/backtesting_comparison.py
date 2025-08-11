#!/usr/bin/env python3
"""
Backtesting de Modelos de Forecasting

Compara 4 enfoques diferentes:
1. SARIMA con todos los meses
2. SARIMA específico al mes a predecir  
3. Regresión lineal con todos los meses
4. Regresión lineal específica al mes a predecir

Evalúa performance usando backtesting temporal.
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

# Crear directorio de resultados
RESULTS_DIR = Path(__file__).parent.parent / "data" / "backtesting"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Imports internos
from sales_engine.forecaster.sales_forcaster import SalesForecaster

class BacktestingComparison:
    """Sistema de backtesting para comparar diferentes enfoques de forecasting."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.forecaster = SalesForecaster(use_test_odoo=use_test_odoo)
        
        # Configuración de backtesting
        self.train_start_year = 2016
        self.test_years = [2022, 2023, 2024]  # Años a predecir
        self.min_history_years = 3  # Mínimo 3 años de historia
        
        print("🔬 BacktestingComparison inicializado")
        print(f"📅 Años de prueba: {self.test_years}")
        print(f"📊 Mínimo años de historia: {self.min_history_years}")
    
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
    
    def filter_skus_for_backtesting(self, data: pd.DataFrame) -> List[str]:
        """Filtrar SKUs que tienen suficientes datos para backtesting confiable."""
        print("\n🔍 Filtrando SKUs para backtesting...")
        
        valid_skus = []
        
        for sku in data['sku'].unique():
            sku_data = data[data['sku'] == sku].copy()
            
            # Verificar que tenga datos en múltiples años
            years_with_data = sku_data['month'].dt.year.nunique()
            
            # Verificar que tenga datos antes del primer año de prueba
            min_test_year = min(self.test_years)
            pre_test_data = sku_data[sku_data['month'].dt.year < min_test_year]
            
            # Verificar volumen mínimo
            total_quantity = sku_data['total_quantity'].sum()
            
            # Criterios de filtrado
            if (years_with_data >= self.min_history_years and 
                len(pre_test_data) >= 24 and  # Al menos 24 meses de historia
                total_quantity >= 50):  # Al menos 50 unidades vendidas en total
                valid_skus.append(sku)
        
        print(f"✅ SKUs válidos para backtesting: {len(valid_skus)} de {data['sku'].nunique()}")
        return valid_skus
    
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
        
        # Features estacionales (sin dummies para evitar multicolinealidad)
        df['month_sin'] = np.sin(2 * np.pi * df['month_num'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month_num'] / 12)
        
        # Lags (si hay suficientes datos)
        if len(df) >= 13:
            df['lag_12'] = df['total_quantity'].shift(12)  # Mismo mes año anterior
        if len(df) >= 25:
            df['lag_24'] = df['total_quantity'].shift(24)  # Mismo mes hace 2 años
        
        # Rolling means
        if len(df) >= 6:
            df['rolling_6m'] = df['total_quantity'].rolling(6, min_periods=3).mean()
        if len(df) >= 12:
            df['rolling_12m'] = df['total_quantity'].rolling(12, min_periods=6).mean()
        
        return df
    
    def create_features_same_month(self, ts_data: pd.DataFrame, target_month: int) -> pd.DataFrame:
        """Crear features para regresión lineal usando solo el mismo mes."""
        df = ts_data.copy()
        
        # Filtrar solo el mes objetivo
        df = df[df['month'].dt.month == target_month].copy()
        df = df.sort_values('month').reset_index(drop=True)
        
        if len(df) < 3:  # Necesitamos al menos 3 años del mismo mes
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
    
    def forecast_sarima_all_months(self, train_data: pd.DataFrame, steps: int = 12) -> Optional[pd.Series]:
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
    
    def forecast_linear_all_months(self, train_data: pd.DataFrame, target_month: int, target_year: int) -> Optional[float]:
        """Regresión lineal usando todos los meses."""
        try:
            # Crear features
            df_features = self.create_features_all_months(train_data)
            
            # Remover filas con NaN (debido a lags)
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
            
            # Verificar que todas las columnas existen
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
            
            # Estimar lag_12 basado en el año anterior del mismo mes
            lag_12_value = 0
            if target_month <= 12:  # Si estamos prediciendo dentro del mismo año
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
                pred_features['lag_24'] = 0  # Aproximación
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
            if len(available_cols) == 1:
                # Solo tendencia temporal
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
            else:
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
    
    def add_covid_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega la variable exógena covid_flag=1 entre 2020-01 y 2023-06, 0 en el resto."""
        df = df.copy()
        df['covid_flag'] = 0
        covid_start = pd.Timestamp('2020-01-01')
        covid_end = pd.Timestamp('2023-06-30')
        mask = (df['month'] >= covid_start) & (df['month'] <= covid_end)
        df.loc[mask, 'covid_flag'] = 1
        return df

    def forecast_sarimax_all_months(self, train_data: pd.DataFrame, steps: int = 12) -> Optional[pd.Series]:
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

    def run_backtesting_for_sku(self, sku: str, data: pd.DataFrame) -> dict:
        """Ejecutar backtesting para un SKU específico usando todos los enfoques."""
        results = {}
        sku_data = data[data['sku'] == sku].copy()
        sku_data = sku_data.sort_values('month')
        sku_data = sku_data.reset_index(drop=True)
        sku_data = self.add_covid_flag(sku_data)
        results = {
            'sku': sku,
            'predictions': {},
            'actuals': {},
            'errors': {},
            'debug_info': {
                'productivo_success_count': 0,
                'productivo_total_attempts': 0,
                'productivo_failures': []
            }
        }
        
        for test_year in self.test_years:
            train_data = sku_data[sku_data['month'].dt.year < test_year].copy()
            test_data = sku_data[sku_data['month'].dt.year == test_year].copy()
            if len(train_data) < 24 or len(test_data) == 0:
                continue
            train_data = self.add_covid_flag(train_data)
            test_data = self.add_covid_flag(test_data)
            
            # Calcular forecast productivo para este año usando solo datos de entrenamiento
            try:
                train_ts = train_data.set_index('month')['total_quantity']
                results['debug_info']['productivo_total_attempts'] += 1
                
                # Debug: mostrar características de los datos de entrenamiento
                zero_pct = (train_ts == 0).sum() / len(train_ts)
                total_sales = train_ts.sum()
                max_val = train_ts.max()
                
                print(f"    🔍 SKU {sku} año {test_year}: train_len={len(train_ts)}, zeros={zero_pct:.1%}, total={total_sales}, max={max_val}")
                
                forecast_prod_year = self.forecaster._forecast_single_sku(train_ts)
                
                # Extraer forecasts mensuales del año de prueba
                prod_forecasts_by_month = {}
                if forecast_prod_year is not None:
                    results['debug_info']['productivo_success_count'] += 1
                    for i, forecast_val in enumerate(forecast_prod_year):
                        # Los forecasts empiezan desde el siguiente mes después del último de entrenamiento
                        last_train_month = train_data['month'].max()
                        forecast_month = last_train_month + pd.DateOffset(months=i+1)
                        if forecast_month.year == test_year:
                            prod_forecasts_by_month[forecast_month.month] = forecast_val
                    print(f"    ✅ Productivo exitoso para SKU {sku} año {test_year}")
                else:
                    results['debug_info']['productivo_failures'].append(f"año_{test_year}")
                    print(f"    ❌ Productivo falló para SKU {sku} año {test_year}")
                    
            except Exception as e:
                print(f"    ❌ Error en forecaster productivo para {sku} año {test_year}: {e}")
                results['debug_info']['productivo_failures'].append(f"año_{test_year}_exception")
                prod_forecasts_by_month = {}
            
            year_predictions = {}
            year_actuals = {}
            
            for _, test_row in test_data.iterrows():
                target_month = test_row['month'].month
                target_year = test_row['month'].year
                actual_value = test_row['total_quantity']
                
                # SARIMA todos los meses
                if test_year not in year_predictions:
                    sarima_all_forecast = self.forecast_sarima_all_months(train_data, 12)
                    year_predictions['sarima_all'] = {}
                    if sarima_all_forecast is not None:
                        for i, pred in enumerate(sarima_all_forecast):
                            month_num = ((target_month - 1 + i) % 12) + 1
                            year_predictions['sarima_all'][month_num] = pred
                pred_sarima_all = year_predictions.get('sarima_all', {}).get(target_month, None)
                
                # SARIMA mismo mes
                pred_sarima_same = self.forecast_sarima_same_month(train_data, target_month)
                
                # Linear todos los meses
                pred_linear_all = self.forecast_linear_all_months(train_data, target_month, target_year)
                
                # Linear mismo mes
                pred_linear_same = self.forecast_linear_same_month(train_data, target_month, target_year)
                
                # SARIMAX todos los meses
                if test_year not in year_predictions:
                    sarimax_all_forecast = self.forecast_sarimax_all_months(train_data, 12)
                    year_predictions['sarimax_all'] = {}
                    if sarimax_all_forecast is not None:
                        for i, pred in enumerate(sarimax_all_forecast):
                            month_num = ((target_month - 1 + i) % 12) + 1
                            year_predictions['sarimax_all'][month_num] = pred
                pred_sarimax_all = year_predictions.get('sarimax_all', {}).get(target_month, None)
                
                # SARIMAX mismo mes
                pred_sarimax_same = self.forecast_sarimax_same_month(train_data, target_month)
                
                # Forecaster productivo
                pred_productivo = prod_forecasts_by_month.get(target_month, None)
                
                # Guardar resultados
                month_key = f"{target_year}-{target_month:02d}"
                year_predictions[month_key] = {
                    'sarima_all': pred_sarima_all,
                    'sarima_same': pred_sarima_same,
                    'linear_all': pred_linear_all,
                    'linear_same': pred_linear_same,
                    'sarimax_all': pred_sarimax_all,
                    'sarimax_same': pred_sarimax_same,
                    'productivo': pred_productivo
                }
                year_actuals[month_key] = actual_value
            
            results['predictions'].update(year_predictions)
            results['actuals'].update(year_actuals)
        
        return results

    def calculate_metrics(self, results: list) -> pd.DataFrame:
        print("\n📊 Calculando métricas de error...")
        all_predictions = {
            'sarima_all': [],
            'sarima_same': [],
            'linear_all': [],
            'linear_same': [],
            'sarimax_all': [],
            'sarimax_same': [],
            'productivo': []  # Agregar el forecaster productivo
        }
        all_actuals = []
        for sku_result in results:
            for month_key, actual in sku_result['actuals'].items():
                if month_key in sku_result['predictions']:
                    preds = sku_result['predictions'][month_key]
                    all_actuals.append(actual)
                    for model_name in all_predictions.keys():
                        pred_value = preds.get(model_name)
                        if pred_value is not None and not pd.isna(pred_value):
                            all_predictions[model_name].append(pred_value)
                        else:
                            all_predictions[model_name].append(np.nan)
        metrics_data = []
        for model_name, predictions in all_predictions.items():
            valid_indices = ~(np.isnan(predictions) | np.isnan(all_actuals))
            valid_preds = np.array(predictions)[valid_indices]
            valid_actuals = np.array(all_actuals)[valid_indices]
            if len(valid_preds) == 0:
                continue
            mae = mean_absolute_error(valid_actuals, valid_preds)
            mse = mean_squared_error(valid_actuals, valid_preds)
            rmse = np.sqrt(mse)
            valid_actuals_nonzero = valid_actuals[valid_actuals != 0]
            valid_preds_nonzero = valid_preds[valid_actuals != 0]
            if len(valid_actuals_nonzero) > 0:
                mape = mean_absolute_percentage_error(valid_actuals_nonzero, valid_preds_nonzero) * 100
            else:
                mape = np.nan
            abs_errors = np.abs(valid_actuals - valid_preds)
            variability = np.std(abs_errors)
            ss_tot = np.sum((valid_actuals - np.mean(valid_actuals)) ** 2)
            ss_res = np.sum((valid_actuals - valid_preds) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else np.nan
            metrics_data.append({
                'model': model_name,
                'n_predictions': len(valid_preds),
                'mae': mae,
                'mse': mse,
                'rmse': rmse,
                'mape': mape,
                'variability': variability,
                'r2': r2
            })
        metrics_df = pd.DataFrame(metrics_data)
        return metrics_df
    
    def run_full_backtesting(self) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """Ejecutar backtesting completo."""
        print("\n🚀 Iniciando backtesting completo...")
        
        # Obtener datos
        with self.forecaster:
            data = self.get_data()
        
        # Filtrar SKUs válidos
        valid_skus = self.filter_skus_for_backtesting(data)
        
        if len(valid_skus) == 0:
            raise ValueError("No se encontraron SKUs válidos para backtesting")
        
        # Limitar a una muestra aleatoria más grande
        import random
        random.seed(42)  # Para reproducibilidad
        test_skus = random.sample(valid_skus, min(100, len(valid_skus)))  # Muestra aleatoria de 100 SKUs
        print(f"🎯 Ejecutando backtesting en {len(test_skus)} SKUs aleatorios de muestra")
        
        # Ejecutar backtesting para cada SKU
        all_results = []
        
        for i, sku in enumerate(test_skus):
            print(f"  📦 ({i+1}/{len(test_skus)}) Procesando SKU: {sku}")
            
            try:
                sku_results = self.run_backtesting_for_sku(sku, data)
                if sku_results['predictions']:  # Solo agregar si tiene predicciones
                    all_results.append(sku_results)
            except Exception as e:
                print(f"    ❌ Error procesando {sku}: {str(e)}")
                continue
        
        print(f"\n✅ Backtesting completado para {len(all_results)} SKUs")
        
        # Mostrar estadísticas del forecaster productivo
        total_attempts = sum(r['debug_info']['productivo_total_attempts'] for r in all_results)
        total_successes = sum(r['debug_info']['productivo_success_count'] for r in all_results)
        success_rate = total_successes / total_attempts if total_attempts > 0 else 0
        
        print(f"\n📊 ESTADÍSTICAS FORECASTER PRODUCTIVO:")
        print(f"   🎯 Intentos totales: {total_attempts}")
        print(f"   ✅ Éxitos: {total_successes}")
        print(f"   📈 Tasa de éxito: {success_rate:.1%}")
        
        if success_rate < 0.5:
            print(f"   ⚠️  ADVERTENCIA: Baja tasa de éxito del forecaster productivo!")
            print(f"   💡 Esto explica por qué tiene métricas pobres en el backtesting")
        
        # Calcular métricas
        metrics_df = self.calculate_metrics(all_results)
        
        return metrics_df, all_results
    
    def save_results(self, metrics_df: pd.DataFrame, all_results: List[Dict[str, Any]]):
        """Guardar resultados del backtesting."""
        print(f"\n💾 Guardando resultados en {RESULTS_DIR}")
        
        # Timestamp para archivos
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Métricas de resumen
        metrics_file = RESULTS_DIR / f"backtesting_metrics_{timestamp}.csv"
        metrics_df.to_csv(metrics_file, index=False)
        print(f"📊 Métricas guardadas: {metrics_file}")
        
        # 2. Resultados detallados
        detailed_results = []
        for result in all_results:
            for month_key, actual in result['actuals'].items():
                if month_key in result['predictions']:
                    preds = result['predictions'][month_key]
                    row = {
                        'sku': result['sku'],
                        'month': month_key,
                        'actual': actual,
                        'pred_sarima_all': preds.get('sarima_all'),
                        'pred_sarima_same': preds.get('sarima_same'),
                        'pred_linear_all': preds.get('linear_all'),
                        'pred_linear_same': preds.get('linear_same'),
                        'pred_sarimax_all': preds.get('sarimax_all'),
                        'pred_sarimax_same': preds.get('sarimax_same'),
                        'pred_productivo': preds.get('productivo')
                    }
                    detailed_results.append(row)
        
        detailed_df = pd.DataFrame(detailed_results)
        detailed_file = RESULTS_DIR / f"backtesting_detailed_{timestamp}.csv"
        detailed_df.to_csv(detailed_file, index=False)
        print(f"📋 Resultados detallados guardados: {detailed_file}")
        
        return metrics_file, detailed_file
    
    def display_results(self, metrics_df: pd.DataFrame):
        """Mostrar resumen de resultados."""
        print("\n" + "="*80)
        print("📊 RESULTADOS DEL BACKTESTING")
        print("="*80)
        
        if metrics_df.empty:
            print("❌ No se pudieron calcular métricas")
            return
        
        # Ordenar por variabilidad (menor es mejor)
        metrics_sorted = metrics_df.sort_values('variability').reset_index(drop=True)
        
        print("\n🏆 RANKING POR VARIABILIDAD (menor es mejor):")
        print("-" * 60)
        print(f"{'Rank':<4} {'Modelo':<20} {'N':<6} {'Variabilidad':<12} {'MAE':<8} {'RMSE':<8} {'MAPE':<8} {'R²':<8}")
        print("-" * 60)
        
        for i, row in metrics_sorted.iterrows():
            highlight = " ⭐️" if row['model'] == 'productivo' else ""
            print(f"{i+1:<4} {row['model']:<20}{highlight} {row['n_predictions']:<6.0f} {row['variability']:<12.2f} {row['mae']:<8.2f} {row['rmse']:<8.2f} {row['mape']:<8.1f}% {row['r2']:<8.3f}")
        
        # Mejor modelo
        best_model = metrics_sorted.iloc[0]
        print(f"\n🥇 MEJOR MODELO: {best_model['model']}")
        print(f"   📊 Variabilidad: {best_model['variability']:.2f}")
        print(f"   📈 MAE: {best_model['mae']:.2f}")
        print(f"   📈 RMSE: {best_model['rmse']:.2f}")
        print(f"   📈 MAPE: {best_model['mape']:.1f}%")
        print(f"   📈 R²: {best_model['r2']:.3f}")
        
        # Comparación de enfoques
        print(f"\n📈 COMPARACIÓN DE ENFOQUES:")
        sarima_models = metrics_sorted[metrics_sorted['model'].str.contains('sarima')]
        linear_models = metrics_sorted[metrics_sorted['model'].str.contains('linear')]
        
        if not sarima_models.empty:
            best_sarima = sarima_models.iloc[0]
            print(f"   🔮 Mejor SARIMA: {best_sarima['model']} (variabilidad: {best_sarima['variability']:.2f})")
        
        if not linear_models.empty:
            best_linear = linear_models.iloc[0]
            print(f"   📏 Mejor Linear: {best_linear['model']} (variabilidad: {best_linear['variability']:.2f})")
        
        # Resaltar el modelo productivo
        prod = metrics_sorted[metrics_sorted['model'] == 'productivo']
        if not prod.empty:
            print(f"\n⭐️ Forecaster productivo: Variabilidad={prod.iloc[0]['variability']:.2f}, MAE={prod.iloc[0]['mae']:.2f}, RMSE={prod.iloc[0]['rmse']:.2f}, MAPE={prod.iloc[0]['mape']:.1f}%, R²={prod.iloc[0]['r2']:.3f}")
        print(f"\n💡 INTERPRETACIÓN:")
        print(f"   • Variabilidad mide la consistencia de las predicciones")
        print(f"   • MAE es el error promedio absoluto")
        print(f"   • MAPE es el error porcentual promedio")
        print(f"   • R² indica qué tan bien el modelo explica la varianza")

    def display_january_2025_forecasts(self, detailed_df: pd.DataFrame, skus: list):
        """Mostrar cómo cada modelo predijo enero 2025 para los SKUs indicados."""
        print("\n📅 FORECASTS PARA ENERO 2025 (SKUs seleccionados)")
        print("="*80)
        
        # Buscar datos para enero 2025 (2025-01)
        target_month_key = "2025-01"
        
        results_found = False
        
        for sku in skus:
            print(f"\n📦 SKU {sku}:")
            print("-" * 40)
            
            # Filtrar datos para este SKU y enero 2025
            sku_data = detailed_df[detailed_df['sku'] == str(sku)]
            january_data = sku_data[sku_data['month'] == target_month_key]
            
            if january_data.empty:
                print(f"   ❌ Sin datos para enero 2025")
                continue
                
            results_found = True
            actual_value = january_data['actual'].iloc[0]
            
            print(f"   📊 Valor real: {actual_value}")
            print(f"   {'Modelo':<20} {'Forecast':<10} {'Error %':<10}")
            print("   " + "-" * 40)
            
            # Mostrar predicciones de cada modelo
            models = ['pred_sarima_all', 'pred_sarima_same', 'pred_linear_all', 
                     'pred_linear_same', 'pred_sarimax_all', 'pred_sarimax_same', 'pred_productivo']
            model_names = ['SARIMA (todos)', 'SARIMA (mismo)', 'Linear (todos)', 
                          'Linear (mismo)', 'SARIMAX (todos)', 'SARIMAX (mismo)', 'Productivo']
            
            for model_col, model_name in zip(models, model_names):
                if model_col in january_data.columns:
                    forecast_val = january_data[model_col].iloc[0]
                    if pd.notna(forecast_val) and forecast_val is not None:
                        # Calcular error porcentual
                        if actual_value != 0:
                            error_pct = ((forecast_val - actual_value) / actual_value) * 100
                        else:
                            error_pct = float('inf') if forecast_val != 0 else 0
                        
                        print(f"   {model_name:<20} {forecast_val:<10.0f} {error_pct:<10.1f}%")
                    else:
                        print(f"   {model_name:<20} {'N/A':<10} {'N/A':<10}")
        
        if not results_found:
            print("❌ No se encontraron datos para enero 2025 en los SKUs especificados")
            print("💡 Esto puede indicar que estos SKUs no tuvieron ventas en enero 2025")
            print("   o que no pasaron los filtros de backtesting")
            
            # Mostrar qué SKUs están disponibles
            available_skus = detailed_df['sku'].unique()
            print(f"\n📋 SKUs disponibles en el dataset: {list(available_skus)[:10]}...")  # Mostrar primeros 10

    def generate_january_2025_forecasts(self, data: pd.DataFrame, target_skus: List[str]) -> pd.DataFrame:
        """Generar forecasts para enero 2025 usando todos los datos históricos disponibles."""
        print("\n🔮 GENERANDO FORECASTS PARA ENERO 2025")
        print("="*60)
        
        results = []
        
        with self.forecaster:  # Context manager para el forecaster
            for sku in target_skus:
                print(f"\n📦 Procesando SKU {sku}:")
                
                sku_data = data[data['sku'] == str(sku)].copy()
                if sku_data.empty:
                    print(f"   ❌ SKU {sku} no encontrado en el dataset")
                    continue
                    
                sku_data = sku_data.sort_values('month')
                sku_data = self.add_covid_flag(sku_data)
                
                # Usar todos los datos históricos hasta diciembre 2024
                all_historical = sku_data[sku_data['month'] <= '2024-12-31'].copy()
                
                if len(all_historical) < 24:
                    print(f"   ❌ SKU {sku}: Datos insuficientes ({len(all_historical)} meses)")
                    continue
                
                # Verificar si tenemos el valor real de enero 2025
                january_2025_actual = None
                january_2025_data = sku_data[sku_data['month'] == '2025-01-31']
                if not january_2025_data.empty:
                    january_2025_actual = january_2025_data['total_quantity'].iloc[0]
                    print(f"   📊 Valor real enero 2025: {january_2025_actual}")
                else:
                    print(f"   ⚠️  Valor real enero 2025: No disponible")
                
                # Generar forecasts con cada modelo
                forecasts = {}
                
                # 1. SARIMA todos los meses
                try:
                    sarima_forecast = self.forecast_sarima_all_months(all_historical, 1)
                    forecasts['SARIMA (todos)'] = sarima_forecast.iloc[0] if sarima_forecast is not None else None
                except:
                    forecasts['SARIMA (todos)'] = None
                
                # 2. SARIMA mismo mes (enero)
                try:
                    forecasts['SARIMA (enero)'] = self.forecast_sarima_same_month(all_historical, 1)
                except:
                    forecasts['SARIMA (enero)'] = None
                
                # 3. Linear todos los meses
                try:
                    forecasts['Linear (todos)'] = self.forecast_linear_all_months(all_historical, 1, 2025)
                except:
                    forecasts['Linear (todos)'] = None
                
                # 4. Linear mismo mes
                try:
                    forecasts['Linear (enero)'] = self.forecast_linear_same_month(all_historical, 1, 2025)
                except:
                    forecasts['Linear (enero)'] = None
                
                # 5. SARIMAX todos los meses
                try:
                    sarimax_forecast = self.forecast_sarimax_all_months(all_historical, 1)
                    forecasts['SARIMAX (todos)'] = sarimax_forecast.iloc[0] if sarimax_forecast is not None else None
                except:
                    forecasts['SARIMAX (todos)'] = None
                
                # 6. SARIMAX mismo mes
                try:
                    forecasts['SARIMAX (enero)'] = self.forecast_sarimax_same_month(all_historical, 1)
                except:
                    forecasts['SARIMAX (enero)'] = None
                
                # 7. Forecaster productivo
                try:
                    ts_data = all_historical.set_index('month')['total_quantity']
                    prod_forecast = self.forecaster._forecast_single_sku(ts_data, steps=1)
                    forecasts['Productivo'] = prod_forecast.iloc[0] if prod_forecast is not None else None
                except Exception as e:
                    print(f"   ❌ Error en forecaster productivo: {e}")
                    forecasts['Productivo'] = None
                
                # Crear resultados para este SKU
                for model_name, forecast_value in forecasts.items():
                    error_pct = None
                    if forecast_value is not None and january_2025_actual is not None:
                        if january_2025_actual != 0:
                            error_pct = ((forecast_value - january_2025_actual) / january_2025_actual) * 100
                        else:
                            error_pct = float('inf') if forecast_value != 0 else 0
                    
                    results.append({
                        'sku': sku,
                        'modelo': model_name,
                        'forecast': forecast_value,
                        'real': january_2025_actual,
                        'error_pct': error_pct
                    })
        
        return pd.DataFrame(results)
    
    def display_january_2025_analysis(self, results_df: pd.DataFrame):
        """Mostrar análisis detallado de forecasts para enero 2025."""
        print("\n📊 ANÁLISIS DE FORECASTS ENERO 2025")
        print("="*80)
        
        if results_df.empty:
            print("❌ No se generaron forecasts para los SKUs solicitados")
            return
        
        for sku in results_df['sku'].unique():
            sku_data = results_df[results_df['sku'] == sku]
            
            print(f"\n📦 SKU {sku}:")
            print("-" * 50)
            
            # Mostrar valor real si existe
            real_value = sku_data['real'].iloc[0]
            if pd.notna(real_value):
                print(f"   📊 Valor real enero 2025: {real_value:.0f} unidades")
            else:
                print(f"   ⚠️  Valor real enero 2025: No disponible")
            
            print(f"\n   {'Modelo':<20} {'Forecast':<12} {'Error %':<12} {'Estado'}")
            print("   " + "-" * 55)
            
            # Mostrar forecasts ordenados por error absoluto (si hay valor real)
            if pd.notna(real_value):
                sku_sorted = sku_data.dropna(subset=['error_pct']).sort_values('error_pct', key=abs)
            else:
                sku_sorted = sku_data.dropna(subset=['forecast'])
            
            for _, row in sku_sorted.iterrows():
                model = row['modelo']
                forecast = row['forecast']
                error = row['error_pct']
                
                if pd.isna(forecast):
                    print(f"   {model:<20} {'N/A':<12} {'N/A':<12} ❌ Falló")
                else:
                    if pd.notna(error):
                        status = "✅ Bueno" if abs(error) < 20 else "⚠️ Regular" if abs(error) < 50 else "❌ Malo"
                        print(f"   {model:<20} {forecast:<12.0f} {error:<12.1f}% {status}")
                    else:
                        print(f"   {model:<20} {forecast:<12.0f} {'N/A':<12} ⚠️ Sin real")
            
            # Mejor modelo para este SKU
            if pd.notna(real_value):
                valid_forecasts = sku_sorted.dropna(subset=['error_pct'])
                if not valid_forecasts.empty:
                    best_model = valid_forecasts.iloc[0]
                    print(f"\n   🏆 Mejor modelo: {best_model['modelo']} (error: {best_model['error_pct']:.1f}%)")
        
        # Resumen general
        print(f"\n📈 RESUMEN GENERAL:")
        print("-" * 30)
        
        # Contar éxitos/fallos por modelo
        model_stats = results_df.groupby('modelo').agg({
            'forecast': lambda x: x.notna().sum(),  # Forecasts exitosos
            'error_pct': lambda x: x.notna().sum()   # Errores calculables
        }).rename(columns={'forecast': 'exitos', 'error_pct': 'con_real'})
        
        total_skus = len(results_df['sku'].unique())
        model_stats['tasa_exito'] = model_stats['exitos'] / total_skus * 100
        
        print(f"{'Modelo':<20} {'Éxitos':<8} {'Tasa':<8}")
        print("-" * 36)
        for model, stats in model_stats.iterrows():
            print(f"{model:<20} {stats['exitos']:<8} {stats['tasa_exito']:<8.1f}%")
        
        # Promedio de errores (solo si hay valores reales)
        errors_by_model = results_df.dropna(subset=['error_pct']).groupby('modelo')['error_pct'].agg(['mean', 'std'])
        if not errors_by_model.empty:
            print(f"\n📊 ERRORES PROMEDIO (solo SKUs con valor real):")
            print(f"{'Modelo':<20} {'Error Medio':<12} {'Desv. Est.':<12}")
            print("-" * 44)
            for model, stats in errors_by_model.iterrows():
                print(f"{model:<20} {stats['mean']:<12.1f}% {stats['std']:<12.1f}%")

    def analyze_specific_skus_january_2025(self, data: pd.DataFrame) -> None:
        """Análisis específico para SKUs 5851, 6434, 5958 en enero 2025."""
        print("\n" + "="*80)
        print("📅 ANÁLISIS ESPECÍFICO: ENERO 2025 - SKUs 5851, 6434, 5958")
        print("="*80)
        
        target_skus = [5851, 6434, 5958]
        
        with self.forecaster:
            for sku in target_skus:
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
                
                # Resumen para este SKU
                if actual_value is not None:
                    forecasts = [
                        ("SARIMA (todos)", pred_sarima),
                        ("SARIMA (enero)", pred_sarima_same),
                        ("Linear (todos)", pred_linear),
                        ("Linear (enero)", pred_linear_same),
                        ("SARIMAX (todos)", pred_sarimax),
                        ("SARIMAX (enero)", pred_sarimax_same),
                        ("Productivo", pred_productivo)
                    ]
                    
                    valid_forecasts = [(name, pred) for name, pred in forecasts if pred is not None]
                    if valid_forecasts:
                        errors = [(name, abs((pred - actual_value) / actual_value * 100)) 
                                for name, pred in valid_forecasts if actual_value != 0]
                        if errors:
                            best_model = min(errors, key=lambda x: x[1])
                            print(f"\n   🏆 Mejor modelo para SKU {sku}: {best_model[0]} (error: {best_model[1]:.1f}%)")
    
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


def main():
    """Función principal."""
    print("🔬 BACKTESTING DE MODELOS DE FORECASTING")
    print("=" * 70)
    print("Comparando 5 enfoques:")
    print("  1. SARIMA con todos los meses")
    print("  2. SARIMA específico al mes a predecir")
    print("  3. Regresión lineal con todos los meses")
    print("  4. Regresión lineal específica al mes a predecir")
    print("  5. Forecaster productivo (SalesForecaster real)")
    print("=" * 70)
    
    try:
        # Inicializar sistema de backtesting
        backtester = BacktestingComparison()
        
        # Ejecutar backtesting
        metrics_df, all_results = backtester.run_full_backtesting()
        
        # Guardar resultados
        metrics_file, detailed_file = backtester.save_results(metrics_df, all_results)
        
        # Mostrar resultados
        backtester.display_results(metrics_df)
        
        # Análisis específico para SKUs 5851, 6434, 5958 en enero 2025
        try:
            # Reutilizar los datos ya cargados durante el backtesting
            data = backtester.get_data()
            backtester.analyze_specific_skus_january_2025(data)
        except Exception as e:
            print(f"⚠️  No se pudo generar el análisis específico de enero 2025: {e}")
            print(f"Error details: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print(f"\n" + "="*70)
        print("✅ BACKTESTING COMPLETADO")
        print("="*70)
        print(f"📊 Métricas: {metrics_file}")
        print(f"📋 Detalles: {detailed_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error durante backtesting: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 