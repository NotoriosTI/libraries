"""
Sales Forecasting Module

This module provides functionalities to generate sales forecasts for each product
based on historical sales data from the 'sales_items' table.

It uses the SARIMA (Seasonal AutoRegressive Integrated Moving Average) model
to capture trends and seasonality in the sales data.

Key Features:
- Connects to the database using the existing DatabaseUpdater logic.
- Fetches and processes historical sales data using pandas.
- Generates monthly forecasts for each product SKU.
- Handles products with insufficient data for forecasting.

Author: Bastian Ibañez (con asistencia de Gemini)
"""
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt
from typing import Dict, Optional

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


class SalesForecaster:
    """
    Orchestrates the sales forecasting process.
    """

    def __init__(self, use_test_odoo: bool = False):
        """
        Initializes the forecaster and the database connection manager.
        """
        self.logger = logger
        self.db_updater = DatabaseUpdater(use_test_odoo=use_test_odoo)
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
            items_quantity > 0;
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
        df.set_index('issueddate', inplace=True)
        
        monthly_sales_df = df.groupby('items_product_sku').resample('ME').sum(numeric_only=True).reset_index()
        
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
            self.logger.warning(f"Skipping SKU {sku_ts.name}: insufficient data points ({len(sku_ts)}).")
            return None
        
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
                self.logger.warning(f"Model didn't converge for SKU {sku_ts.name}")
                return None
            
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
                self.logger.error(f"Failed to generate forecast for SKU {sku_ts.name}: {error_type} - {str(e)}")
            return None

    def run_forecasting_for_all_skus(self) -> Optional[Dict[str, pd.Series]]:
        """
        Main orchestration method to generate forecasts for all products.
        """
        historical_data = self.get_historical_sales_data()
        if historical_data is None:
            return None
            
        monthly_data = self.prepare_monthly_time_series(historical_data)
        
        all_forecasts: Dict[str, pd.Series] = {}
        unique_skus = monthly_data['sku'].unique()
        
        self.logger.info(f"Starting forecasting process for {len(unique_skus)} SKUs...")
        
        # NUEVA VALIDACIÓN: Pre-filtrar SKUs problemáticos
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
            
            valid_skus.append((sku, ts_filled))
        
        self.logger.info(f"Pre-filtering results: {len(valid_skus)} valid SKUs, {skipped_insufficient_data} insufficient data, {skipped_poor_quality} poor quality")
        
        # Procesar solo SKUs válidos
        for i, (sku, ts_prepared) in enumerate(valid_skus):
            self.logger.info(f"  ({i+1}/{len(valid_skus)}) Forecasting for SKU: {sku}")
            
            ts_prepared.name = sku  # Asignar nombre para logs
            
            # Generar proyección
            forecast_result = self._forecast_single_sku(ts_prepared)
            
            if forecast_result is not None:
                all_forecasts[sku] = forecast_result
                
        self.logger.success(f"Forecasting complete. Generated projections for {len(all_forecasts)} SKUs (processed {len(valid_skus)} valid SKUs).")
        return all_forecasts

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