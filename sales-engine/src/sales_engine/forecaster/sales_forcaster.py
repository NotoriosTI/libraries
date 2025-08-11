"""
Enhanced Sales Forecasting Module with Lifecycle Validation

This module provides functionalities to generate sales forecasts for each product
based on historical sales data from the 'sales_items' table.

It uses the SARIMA (Seasonal AutoRegressive Integrated Moving Average) model
to capture trends and seasonality in the sales data.

Enhanced Features:
- Connects to the database using the existing DatabaseUpdater logic.
- Fetches and processes historical sales data using pandas.
- Generates monthly forecasts for each product SKU.
- 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0
- 📅 Validación temporal: Verificar actividad reciente antes de generar forecast
- 🎯 Clasificación inteligente de productos por estado de ciclo de vida
- Handles products with insufficient data for forecasting.

Author: Bastian Ibañez (con asistencia de Gemini)
"""
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta

# Importar la infraestructura existente
# Asumimos que la estructura de carpetas permite esta importación relativa
from ..db_updater import DatabaseUpdater, DatabaseConnectionError

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("sales-forecaster")
except ImportError:
    class LoggerFallback:
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️  {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
    logger = LoggerFallback()


# Importar validación de ciclo de vida
try:
    from .product_lifecycle_validator import ProductLifecycleValidator, ProductStatus
    LIFECYCLE_VALIDATION_AVAILABLE = True
except ImportError:
    logger.warning("ProductLifecycleValidator no disponible - usando filtros básicos")
    LIFECYCLE_VALIDATION_AVAILABLE = False
    
    # Crear clases mock para mantener compatibilidad
    class ProductStatus:
        ACTIVE = "active"
        INACTIVE = "inactive"
        DISCONTINUED = "discontinued"
        NEW = "new"
        UNKNOWN = "unknown"
    
    class ProductLifecycleValidator:
        def __init__(self, *args, **kwargs):
            pass
        def batch_validate_products(self, *args, **kwargs):
            return {}
        def get_validation_summary(self, *args, **kwargs):
            return {'by_status': {}}


class SalesForecaster:
    """
    Enhanced Sales Forecaster with Lifecycle Validation.
    
    Orchestrates the sales forecasting process with automatic validation
    of product lifecycle to exclude discontinued and inactive products.
    """

    def __init__(self, use_test_odoo: bool = False, enable_lifecycle_validation: bool = True):
        """
        Initializes the forecaster and the database connection manager.
        
        Args:
            use_test_odoo (bool): Si usar datos de test de Odoo
            enable_lifecycle_validation (bool): Si habilitar validación de ciclo de vida
        """
        self.logger = logger
        self.db_updater = DatabaseUpdater(use_test_odoo=use_test_odoo)
        self.enable_lifecycle_validation = enable_lifecycle_validation and LIFECYCLE_VALIDATION_AVAILABLE
        
        if self.enable_lifecycle_validation:
            self.lifecycle_validator = ProductLifecycleValidator(
                discontinued_threshold_days=365,  # 12 meses
                inactive_threshold_days=180,      # 6 meses
                minimum_historical_sales=10,
                new_product_threshold_days=90     # 3 meses
            )
            self.logger.info("SalesForecaster initialized with lifecycle validation enabled.")
        else:
            self.lifecycle_validator = None
            if not LIFECYCLE_VALIDATION_AVAILABLE:
                self.logger.warning("SalesForecaster initialized with basic filtering (lifecycle validation not available).")
            else:
                self.logger.info("SalesForecaster initialized with lifecycle validation disabled.")
        
        self.logger.info("SalesForecaster initialized.")

    def get_historical_sales_data(self) -> Optional[pd.DataFrame]:
        """
        Fetches historical sales data from the database.
        
        Returns:
            A pandas DataFrame with historical sales data, or None on failure.
        """
        self.logger.info("Fetching historical sales data...")
        query = """
        SELECT
            issueddate,
            items_product_sku,
            items_quantity
        FROM
            sales_items
        WHERE
            items_quantity > 0
            AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones');
        """
        try:
            # Usamos el pool de conexiones de DatabaseUpdater
            with self.db_updater.get_connection() as conn:
                df = pd.read_sql(query, conn)
            
            if df.empty:
                self.logger.warning("No historical sales data found in the database.")
                return None

            df['issueddate'] = pd.to_datetime(df['issueddate'])
            self.logger.success(f"Successfully fetched {len(df):,} sales records.")
            return df
        except DatabaseConnectionError as e:
            self.logger.error("Could not connect to the database to fetch sales data.", error=str(e))
            return None
        except Exception as e:
            self.logger.error("An unexpected error occurred while fetching data.", error=str(e))
            return None

    def prepare_monthly_time_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates transactional data into monthly time series for each SKU.
        """
        self.logger.info("Aggregating sales data into monthly time series...")
        
        # Hacer una copia para no modificar el DataFrame original
        df_copy = df.copy()
        df_copy.set_index('issueddate', inplace=True)
        
        monthly_sales_df = df_copy.groupby('items_product_sku').resample('ME').sum(numeric_only=True).reset_index()
        
        monthly_sales_df.rename(columns={
            'issueddate': 'month',
            'items_product_sku': 'sku',
            'items_quantity': 'total_quantity'
        }, inplace=True)
        
        self.logger.success("Time series preparation complete.")
        return monthly_sales_df

    def _forecast_single_sku(self, sku_ts: pd.Series, steps: int = 12) -> Optional[pd.Series]:
        """
        Generates a forecast for a single product's time series using SARIMA.
        
        Args:
            sku_ts: A pandas Series representing the monthly sales of one SKU.
            steps: The number of months to forecast into the future.

        Returns:
            A pandas Series with the forecasted values, or None if forecasting fails.
        """
        # Se necesita un mínimo de datos para que SARIMA funcione (ej: 2 ciclos estacionales)
        if len(sku_ts) < 24:
            self.logger.warning(f"Skipping SARIMA for SKU {sku_ts.name}: insufficient data points ({len(sku_ts)}). Trying linear regression fallback.")
            return self._forecast_with_linear_regression(sku_ts, steps)
        
        # NUEVA VALIDACIÓN: Verificar calidad de datos
        non_zero_count = (sku_ts > 0).sum()
        zero_percentage = (sku_ts == 0).sum() / len(sku_ts)
        
        # Rechazar series con demasiados ceros (>80%)
        if zero_percentage > 0.8:
            self.logger.warning(f"Skipping SKU {sku_ts.name}: too many zeros ({zero_percentage:.1%}).")
            return None
        
        # Rechazar series con valores extremos
        q99 = sku_ts.quantile(0.99)
        q01 = sku_ts.quantile(0.01)
        if q99 > 1000000 or sku_ts.max() > 10 * q99:  # Detectar outliers extremos
            self.logger.warning(f"Skipping SKU {sku_ts.name}: extreme values detected (max: {sku_ts.max()}).")
            return None
        
        try:
            # MEJORA: Usar parámetros más conservadores y estables
            # Modelo SARIMA con parámetros más robustos
            model = sm.tsa.statespace.SARIMAX(
                sku_ts,
                order=(0, 1, 1),  # Más simple y estable
                seasonal_order=(0, 1, 1, 12),  # Estacionalidad más conservadora
                enforce_stationarity=True,  # ✅ Forzar estabilidad
                enforce_invertibility=True  # ✅ Forzar invertibilidad
            )
            
            # Ajustar con manejo de errores más específico
            results = model.fit(disp=False, maxiter=50)  # Limitar iteraciones
            
            # Verificar convergencia del modelo
            if not results.mle_retvals['converged']:
                self.logger.warning(f"Model didn't converge for SKU {sku_ts.name}. Trying linear regression fallback.")
                return self._forecast_with_linear_regression(sku_ts, steps)
            
            # Generar forecast
            forecast = results.get_forecast(steps=steps)
            predicted_values = forecast.predicted_mean
            
            # VALIDACIÓN CRÍTICA: Aplicar límites razonables
            # Calcular límites basados en datos históricos
            historical_max = sku_ts.max()
            historical_mean = sku_ts.mean()
            historical_q95 = sku_ts.quantile(0.95)
            
            # MEJORA: Límite superior más inteligente
            # 1. Usar el máximo de: histórico máximo * 2, percentil 95 * 3, o media * 15
            # 2. Pero con un mínimo razonable de 50 unidades para evitar sobre-restricción
            upper_candidate1 = historical_max * 2
            upper_candidate2 = historical_q95 * 3
            upper_candidate3 = historical_mean * 15
            
            # Tomar el mayor de los candidatos, pero con límites sensatos
            upper_limit = max(
                max(upper_candidate1, upper_candidate2, upper_candidate3),
                50  # Mínimo absoluto para no ser demasiado restrictivo
            )
            
            # Cap absoluto solo para casos realmente extremos
            upper_limit = min(upper_limit, 50000)
            
            lower_limit = 0  # No permitir valores negativos
            
            # Solo aplicar límites si son realmente extremos
            original_max = predicted_values.max()
            predicted_values = predicted_values.clip(lower=lower_limit, upper=upper_limit)
            
            # Log si hubo recorte significativo
            if original_max > upper_limit:
                self.logger.info(f"SKU {sku_ts.name}: Limited forecast from {original_max:.0f} to {upper_limit:.0f}")
            
            # 🚨 NUEVA VALIDACIÓN: Límite de 40% de variación entre meses consecutivos
            predicted_values = self._apply_month_to_month_variation_limit(sku_ts, predicted_values, max_variation=0.40)
            
            # Conversión segura a enteros
            predicted_values = predicted_values.round().astype(int)
            
            # Validación final
            if predicted_values.max() > 100000 or predicted_values.min() < 0:
                self.logger.warning(f"Unrealistic predictions for SKU {sku_ts.name}: {predicted_values.min()}-{predicted_values.max()}")
                return None
            
            self.logger.info(f"Forecast generated for SKU {sku_ts.name}: {predicted_values.min()}-{predicted_values.max()}")
            return predicted_values
            
        except Exception as e:
            # Manejo más específico de errores
            error_type = type(e).__name__
            if "singular" in str(e).lower() or "invertibility" in str(e).lower():
                self.logger.warning(f"Model instability for SKU {sku_ts.name}: {error_type}")
            else:
                self.logger.error(f"Failed to generate forecast for SKU {sku_ts.name}: {error_type} - {str(e)}. Trying linear regression fallback.")
            return self._forecast_with_linear_regression(sku_ts, steps)

    def _forecast_with_linear_regression(self, sku_ts: pd.Series, steps: int = 12) -> Optional[pd.Series]:
        """
        Fallback simple usando regresión lineal sobre la serie mensual.
        Requiere al menos 6 puntos. Aplica los mismos límites y suavizado que SARIMA.
        """
        try:
            # Requerir al menos 6 observaciones reales
            if len(sku_ts) < 6:
                self.logger.warning(f"Skipping Linear Regression for SKU {sku_ts.name}: too few points ({len(sku_ts)}).")
                return None

            # Preparar X,Y
            y = sku_ts.astype(float).values
            x = np.arange(len(y), dtype=float)

            # Ajustar recta y = a*x + b
            slope, intercept = np.polyfit(x, y, 1)

            # Generar predicciones futuras
            future_x = np.arange(len(y), len(y) + steps, dtype=float)
            future_y = intercept + slope * future_x

            # Crear índice de meses futuros (fin de mes)
            last_idx = sku_ts.index[-1]
            if isinstance(last_idx, pd.Timestamp):
                future_periods = pd.period_range(last_idx, periods=steps + 1, freq='M')[1:]
                future_index = future_periods.to_timestamp('M')
            else:
                # Fallback genérico a fechas con frecuencia mensual fin de mes
                last_ts = pd.to_datetime(last_idx)
                future_index = pd.date_range(last_ts, periods=steps + 1, freq='M')[1:]

            predicted_values = pd.Series(future_y, index=future_index)

            # Aplicar límites similares a SARIMA
            historical_max = sku_ts.max()
            historical_mean = sku_ts.mean()
            historical_q95 = sku_ts.quantile(0.95)
            upper_candidate1 = historical_max * 2
            upper_candidate2 = historical_q95 * 3
            upper_candidate3 = historical_mean * 15
            upper_limit = max(max(upper_candidate1, upper_candidate2, upper_candidate3), 50)
            upper_limit = min(upper_limit, 50000)
            lower_limit = 0
            original_max = predicted_values.max()
            predicted_values = predicted_values.clip(lower=lower_limit, upper=upper_limit)
            if original_max > upper_limit:
                self.logger.info(f"[LR] SKU {sku_ts.name}: Limited forecast from {original_max:.0f} to {upper_limit:.0f}")

            # Limitar variación mes a mes 40%
            predicted_values = self._apply_month_to_month_variation_limit(sku_ts, predicted_values, max_variation=0.40)

            # Redondear a enteros y validar
            predicted_values = predicted_values.round().astype(int)
            if predicted_values.max() > 100000 or predicted_values.min() < 0:
                self.logger.warning(f"[LR] Unrealistic predictions for SKU {sku_ts.name}: {predicted_values.min()}-{predicted_values.max()}")
                return None

            self.logger.info(f"[LR] Forecast generated for SKU {sku_ts.name}: {predicted_values.min()}-{predicted_values.max()}")
            return predicted_values
        except Exception as e:
            self.logger.error(f"Linear Regression fallback failed for SKU {sku_ts.name}: {e}")
            return None

    def _apply_month_to_month_variation_limit(self, historical_ts: pd.Series, predicted_values: pd.Series, max_variation: float = 0.40) -> pd.Series:
        """
        Aplica un límite de variación entre meses consecutivos para evitar saltos extremos.
        
        Args:
            historical_ts: Serie temporal histórica para obtener el último valor real
            predicted_values: Predicciones generadas por el modelo
            max_variation: Variación máxima permitida (0.40 = 40%)
            
        Returns:
            Serie de predicciones suavizada con límites de variación
        """
        if len(predicted_values) == 0:
            return predicted_values
            
        # Crear una copia para modificar
        smoothed_predictions = predicted_values.copy()
        
        # Obtener el último valor histórico como punto de referencia
        last_historical_value = historical_ts.iloc[-1] if len(historical_ts) > 0 else predicted_values.iloc[0]
        
        # Si el último valor histórico es 0, usar la media histórica como referencia
        if last_historical_value <= 0:
            last_historical_value = max(historical_ts.mean(), 1)  # Mínimo 1 para evitar división por 0
        
        # Aplicar límites secuencialmente, mes por mes
        previous_value = last_historical_value
        adjustments_made = 0
        
        for i in range(len(smoothed_predictions)):
            current_prediction = smoothed_predictions.iloc[i]
            
            # Calcular límites: +/- max_variation% del valor anterior
            upper_limit = previous_value * (1 + max_variation)
            lower_limit = previous_value * (1 - max_variation)
            
            # Aplicar límites
            original_prediction = current_prediction
            
            if current_prediction > upper_limit:
                smoothed_predictions.iloc[i] = upper_limit
                adjustments_made += 1
            elif current_prediction < lower_limit:
                smoothed_predictions.iloc[i] = lower_limit
                adjustments_made += 1
            
            # El valor ajustado se convierte en la referencia para el siguiente mes
            previous_value = smoothed_predictions.iloc[i]
        
        # Log si se hicieron ajustes significativos
        if adjustments_made > 0:
            original_max_change = abs(predicted_values.iloc[-1] - last_historical_value) / last_historical_value * 100
            smoothed_max_change = abs(smoothed_predictions.iloc[-1] - last_historical_value) / last_historical_value * 100
            
            self.logger.info(f"SKU {historical_ts.name}: Applied {max_variation:.0%} variation limit - "
                           f"{adjustments_made} adjustments made. "
                           f"Max change: {original_max_change:.1f}% → {smoothed_max_change:.1f}%")
        
        return smoothed_predictions

    def run_forecasting_for_all_skus(self) -> Optional[Dict[str, pd.Series]]:
        """
        Main orchestration method to generate forecasts for all products with lifecycle validation.
        """
        self.logger.info("🚀 Starting enhanced forecasting process with lifecycle validation")
        
        # 1. Obtener datos históricos
        historical_data = self.get_historical_sales_data()
        if historical_data is None:
            self.logger.error("No se pudieron obtener datos históricos")
            return None
        
        # 2. Obtener SKUs únicos de datos históricos (antes de procesamiento)
        unique_skus = list(historical_data['items_product_sku'].unique())
        
        # 3. Preparar series temporales mensuales
        monthly_data = self.prepare_monthly_time_series(historical_data)
        
        self.logger.info(f"Datos obtenidos para {len(unique_skus)} SKUs únicos")
        
        # 4. Validación de ciclo de vida (si está habilitada)
        if self.enable_lifecycle_validation:
            validation_results = self._validate_products_lifecycle(historical_data, unique_skus)
            filtered_skus = self._filter_skus_by_lifecycle(unique_skus, validation_results)
        else:
            self.logger.warning("⚠️  Saltando validación de ciclo de vida - usando filtros básicos")
            filtered_skus = self._apply_basic_filters(monthly_data, unique_skus)
            validation_results = {}
        
        self.logger.info(f"SKUs aprobados para forecasting: {len(filtered_skus)}")
        
        # 5. Generar forecasts solo para SKUs válidos
        all_forecasts = self._generate_forecasts_for_valid_skus(
            monthly_data, filtered_skus, validation_results
        )
        
        # 6. Aplicar post-procesamiento basado en ciclo de vida
        if self.enable_lifecycle_validation and all_forecasts:
            all_forecasts = self._apply_lifecycle_adjustments(all_forecasts, validation_results)
        
        self.logger.success(f"Forecasting completado para {len(all_forecasts) if all_forecasts else 0} SKUs")
        
        return all_forecasts

    def _validate_products_lifecycle(self, historical_data: pd.DataFrame, unique_skus: List[str]) -> Dict[str, Dict]:
        """
        Validar ciclo de vida de todos los productos.
        
        Args:
            historical_data (pd.DataFrame): Datos históricos de ventas
            unique_skus (List[str]): Lista de SKUs únicos
            
        Returns:
            Dict[str, Dict]: Resultados de validación por SKU
        """
        self.logger.info("🔍 Validando ciclo de vida de productos")
        
        # Validar que los datos históricos tengan las columnas requeridas
        required_columns = ['issueddate', 'items_product_sku', 'items_quantity']
        missing_columns = [col for col in required_columns if col not in historical_data.columns]
        
        if missing_columns:
            self.logger.error(f"Datos históricos faltantes columnas requeridas: {missing_columns}")
            self.logger.error(f"Columnas disponibles: {list(historical_data.columns)}")
            # Retornar resultados vacíos para todos los SKUs
            return {sku: {
                'status': ProductStatus.UNKNOWN,
                'metadata': {
                    'reason': f'Datos históricos incompletos: faltan {missing_columns}',
                    'should_forecast': False,
                    'recommended_forecast': 0
                }
            } for sku in unique_skus}
        
        # Agrupar historiales por SKU
        skus_with_history = {}
        skus_processed = 0
        skus_with_data = 0
        
        for sku in unique_skus:
            sku_data = historical_data[historical_data['items_product_sku'] == sku].copy()
            
            # Solo incluir columnas que necesita el validador
            if not sku_data.empty:
                sku_data = sku_data[['issueddate', 'items_quantity']].copy()
                skus_with_data += 1
            
            skus_with_history[sku] = sku_data
            skus_processed += 1
        
        self.logger.info(f"Preparados {skus_processed} SKUs para validación ({skus_with_data} con datos)")
        
        # Ejecutar validación en lote
        validation_results = self.lifecycle_validator.batch_validate_products(skus_with_history)
        
        # Log estadísticas de validación
        summary = self.lifecycle_validator.get_validation_summary(validation_results)
        self.logger.info("Resumen de validación de ciclo de vida:", **summary['by_status'])
        
        return validation_results
    
    def _filter_skus_by_lifecycle(self, unique_skus: List[str], validation_results: Dict[str, Dict]) -> List[str]:
        """
        Filtrar SKUs basándose en resultados de validación de ciclo de vida.
        
        Args:
            unique_skus (List[str]): SKUs originales
            validation_results (Dict[str, Dict]): Resultados de validación
            
        Returns:
            List[str]: SKUs que deben generar forecast
        """
        valid_skus = []
        
        stats = {
            'total': len(unique_skus),
            'approved': 0,
            'discontinued': 0,
            'inactive': 0,
            'insufficient_data': 0
        }
        
        for sku in unique_skus:
            if sku in validation_results:
                validation = validation_results[sku]
                metadata = validation['metadata']
                status = validation['status']
                
                if metadata.get('should_forecast', False):
                    valid_skus.append(sku)
                    stats['approved'] += 1
                    
                    # Log productos con advertencias
                    if hasattr(status, 'value'):
                        status_val = status.value
                    else:
                        status_val = str(status)
                    
                    if status_val == ProductStatus.NEW:
                        self.logger.warning(f"SKU {sku}: Producto nuevo - usar forecasts con precaución")
                    elif status_val == ProductStatus.INACTIVE:
                        self.logger.info(f"SKU {sku}: Producto inactivo - forecast conservador")
                else:
                    # Log productos excluidos
                    if hasattr(status, 'value'):
                        status_val = status.value
                    else:
                        status_val = str(status)
                    
                    if status_val == ProductStatus.DISCONTINUED:
                        stats['discontinued'] += 1
                        self.logger.info(f"SKU {sku}: EXCLUIDO - {metadata.get('reason', 'Descontinuado')}")
                    elif status_val == ProductStatus.INACTIVE:
                        stats['inactive'] += 1
                        self.logger.info(f"SKU {sku}: EXCLUIDO - {metadata.get('reason', 'Inactivo')}")
                    else:
                        stats['insufficient_data'] += 1
            else:
                # Sin validación, excluir por seguridad
                stats['insufficient_data'] += 1
                self.logger.warning(f"SKU {sku}: EXCLUIDO - Sin datos de validación")
        
        self.logger.info("Filtrado por ciclo de vida completado", **stats)
        
        return valid_skus
    
    def _apply_basic_filters(self, monthly_data: pd.DataFrame, unique_skus: List[str]) -> List[str]:
        """
        Aplicar filtros básicos cuando la validación de ciclo de vida está deshabilitada.
        
        Args:
            monthly_data (pd.DataFrame): Datos mensuales
            unique_skus (List[str]): SKUs únicos
            
        Returns:
            List[str]: SKUs válidos usando filtros básicos
        """
        valid_skus = []
        skipped_insufficient_data = 0
        skipped_poor_quality = 0
        
        for sku in unique_skus:
            # Preparar la serie de tiempo para este SKU
            ts_individual = monthly_data[monthly_data['sku'] == sku]
            ts_prepared = ts_individual[['month', 'total_quantity']].set_index('month')['total_quantity']
            
            # MEJORA: Solo rellenar huecos pequeños (máximo 3 meses consecutivos)
            # En lugar de rellenar todo con asfreq
            ts_prepared = ts_prepared.resample('ME').sum()  # Esto mantiene NaN para meses sin datos
            
            # Convertir NaN a 0 solo si hay suficientes datos reales
            if ts_prepared.count() < 12:  # Menos de 12 meses con ventas reales
                skipped_insufficient_data += 1
                continue
            
            # Rellenar solo huecos pequeños (interpolación inteligente)
            ts_filled = ts_prepared.fillna(0)
            
            # Validar calidad de datos pre-modelo
            if len(ts_filled) < 24:
                skipped_insufficient_data += 1
                continue
                
            zero_percentage = (ts_filled == 0).sum() / len(ts_filled)
            if zero_percentage > 0.7:  # Más del 70% son ceros
                skipped_poor_quality += 1
                continue
            
            # Verificar que tenga suficientes ventas reales
            total_sales = ts_filled.sum()
            if total_sales < 10:  # Menos de 10 unidades en total
                skipped_poor_quality += 1
                continue
            
            valid_skus.append(sku)
        
        self.logger.info(f"Pre-filtering results: {len(valid_skus)} valid SKUs, {skipped_insufficient_data} insufficient data, {skipped_poor_quality} poor quality")
        
        return valid_skus
    
    def _generate_forecasts_for_valid_skus(self, 
                                         monthly_data: pd.DataFrame, 
                                         valid_skus: List[str],
                                         validation_results: Dict[str, Dict]) -> Dict[str, pd.Series]:
        """
        Generar forecasts solo para SKUs válidos.
        
        Args:
            monthly_data (pd.DataFrame): Datos mensuales
            valid_skus (List[str]): SKUs válidos para forecasting
            validation_results (Dict[str, Dict]): Resultados de validación
            
        Returns:
            Dict[str, pd.Series]: Forecasts generados
        """
        all_forecasts: Dict[str, pd.Series] = {}
        
        self.logger.info(f"Generando forecasts para {len(valid_skus)} SKUs válidos")
        
        for i, sku in enumerate(valid_skus):
            self.logger.info(f"  ({i+1}/{len(valid_skus)}) Forecasting para SKU: {sku}")
            
            try:
                # Preparar serie temporal
                ts_individual = monthly_data[monthly_data['sku'] == sku]
                ts_prepared = ts_individual[['month', 'total_quantity']].set_index('month')['total_quantity']
                ts_prepared = ts_prepared.resample('ME').sum().fillna(0)
                ts_prepared.name = sku
                
                # Ajustar parámetros basándose en estado del producto
                forecast_steps = 12  # Default
                if sku in validation_results:
                    status = validation_results[sku]['status']
                    if hasattr(status, 'value'):
                        status_val = status.value
                    else:
                        status_val = str(status)
                    
                    if status_val == ProductStatus.NEW:
                        forecast_steps = 6  # Forecasts más cortos para productos nuevos
                    elif status_val == ProductStatus.INACTIVE:
                        forecast_steps = 3  # Forecasts muy cortos para inactivos
                
                # Generar forecast usando el método padre
                forecast = self._forecast_single_sku(ts_prepared, steps=forecast_steps)
                
                if forecast is not None:
                    all_forecasts[sku] = forecast
                    self.logger.info(f"    ✅ Forecast generado: {forecast.min():.0f}-{forecast.max():.0f} unidades")
                else:
                    self.logger.warning(f"    ⚠️  Forecast falló para SKU {sku}")
                
            except Exception as e:
                self.logger.error(f"    ❌ Error generando forecast para SKU {sku}: {e}")
                continue
        
        return all_forecasts
    
    def _apply_lifecycle_adjustments(self, 
                                   forecasts: Dict[str, pd.Series], 
                                   validation_results: Dict[str, Dict]) -> Dict[str, pd.Series]:
        """
        Aplicar ajustes post-forecasting basados en ciclo de vida.
        
        Args:
            forecasts (Dict[str, pd.Series]): Forecasts originales
            validation_results (Dict[str, Dict]): Resultados de validación
            
        Returns:
            Dict[str, pd.Series]: Forecasts ajustados
        """
        adjusted_forecasts = {}
        adjustments_made = 0
        
        for sku, forecast in forecasts.items():
            if sku in validation_results:
                status = validation_results[sku]['status']
                metadata = validation_results[sku]['metadata']
                
                if hasattr(status, 'value'):
                    status_val = status.value
                else:
                    status_val = str(status)
                
                # Aplicar ajustes conservadores para productos inactivos
                if status_val == ProductStatus.INACTIVE:
                    # Reducir forecast en 50% para productos inactivos
                    adjusted_forecast = forecast * 0.5
                    adjusted_forecasts[sku] = adjusted_forecast
                    adjustments_made += 1
                    self.logger.info(f"Forecast ajustado para SKU inactivo {sku}: reducido 50%")
                
                # Aplicar límites más estrictos para productos nuevos
                elif status_val == ProductStatus.NEW:
                    # Limitar forecasts de productos nuevos a máximo 20 unidades
                    adjusted_forecast = forecast.clip(upper=20)
                    adjusted_forecasts[sku] = adjusted_forecast
                    
                    if forecast.max() > 20:
                        adjustments_made += 1
                        self.logger.info(f"Forecast limitado para SKU nuevo {sku}: máximo 20 unidades")
                    else:
                        adjusted_forecasts[sku] = forecast
                
                else:
                    # Mantener forecast original para productos activos
                    adjusted_forecasts[sku] = forecast
            else:
                # Sin información de validación, mantener original
                adjusted_forecasts[sku] = forecast
        
        self.logger.info(f"Ajustes post-forecasting aplicados: {adjustments_made} modificaciones")
        
        return adjusted_forecasts
    
    def get_lifecycle_summary(self, validation_results: Dict[str, Dict]) -> Dict:
        """
        Obtener resumen detallado de la validación de ciclo de vida.
        
        Args:
            validation_results (Dict[str, Dict]): Resultados de validación
            
        Returns:
            Dict: Resumen detallado
        """
        if not self.enable_lifecycle_validation or not validation_results:
            return {}
        
        return self.lifecycle_validator.get_validation_summary(validation_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_updater.close()


if __name__ == '__main__':
    # --- CÓMO EJECUTAR EL SCRIPT ---
    # 1. Asegúrate de que el Cloud SQL Proxy esté corriendo.
    # 2. Configura tus credenciales (si no están en un .env, puedes hacerlo aquí).
    
    # El 'with' se asegura de que la conexión a la BD se cierre correctamente.
    with SalesForecaster() as forecaster:
        # Generar las proyecciones para todos los productos
        forecasts = forecaster.run_forecasting_for_all_skus()
        
        if forecasts:
            # Convertir el diccionario de resultados a un DataFrame para mejor visualización
            forecast_df = pd.DataFrame(forecasts)
            
            print("\n--- 🔮 Sales Forecast Results (Next 12 Months) ---")
            print(forecast_df.head())
            
            # Opcional: Guardar los resultados en un archivo CSV
            try:
                output_path = "sales_forecast.csv"
                forecast_df.to_csv(output_path)
                logger.success(f"Forecast results saved to {output_path}")
            except Exception as e:
                logger.error("Could not save forecast results to CSV.", error=str(e))
                
            # Opcional: Visualizar la proyección de un producto específico
            sku_to_plot = forecast_df.columns[0] # Graficar el primer SKU con proyección
            if sku_to_plot:
                plt.figure(figsize=(12, 6))
                forecast_df[sku_to_plot].plot(label='Forecasted Sales', marker='o')
                plt.title(f'Forecast for SKU: {sku_to_plot}')
                plt.xlabel('Month')
                plt.ylabel('Predicted Quantity')
                plt.legend()
                plt.grid(True)
                plt.show()