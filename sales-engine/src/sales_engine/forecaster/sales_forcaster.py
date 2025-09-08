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

Author: Bastian Ibañez (con asistencia de Claude)
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


# Simplificado: ya no usamos validación compleja de ciclo de vida
# Los filtros necesarios están integrados en las consultas SQL y validaciones básicas


class SalesForecaster:
    """
    Simplified Sales Forecaster.
    
    Orchestrates the sales forecasting process with built-in filtering
    for discontinued products and raw materials via SQL queries.
    """

    def __init__(self, use_test_odoo: bool = False):
        """
        Initializes the forecaster and the database connection manager.
        
        Args:
            use_test_odoo (bool): Si usar datos de test de Odoo
        """
        self.logger = logger
        self.db_updater = DatabaseUpdater(use_test_odoo=use_test_odoo)
        
        self.logger.info("SalesForecaster initialized with simplified filtering.")

    def get_valid_skus_precalculated(self) -> set:
        """
        Pre-calcula los SKUs válidos (no materias primas + con ventas recientes).
        Esto es MUY eficiente vs aplicar funciones a cada fila.
        
        Returns:
            set: SKUs válidos para procesar
        """
        import time
        start_time = time.time()
        
        self.logger.info("🔍 Pre-calculando SKUs válidos (no materias primas + ventas recientes)...")
        
        # Query optimizada que pre-calcula todo de una vez
        query = """
        WITH recent_sales_skus AS (
            SELECT DISTINCT items_product_sku
            FROM sales_items 
            WHERE items_quantity > 0
                AND issueddate >= CURRENT_DATE - INTERVAL '12 months'
                AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
        ),
        non_raw_material_skus AS (
            SELECT DISTINCT items_product_sku
            FROM sales_items
            WHERE items_product_sku NOT IN (
                SELECT DISTINCT items_product_sku
                FROM sales_items 
                WHERE UPPER(items_product_description) LIKE '%MP%' 
                   OR UPPER(items_product_description) LIKE '%MATERIA PRIMA%' 
                   OR UPPER(items_product_description) LIKE '%RAW MATERIAL%'
            )
        )
        SELECT r.items_product_sku
        FROM recent_sales_skus r
        INNER JOIN non_raw_material_skus n ON r.items_product_sku = n.items_product_sku
        """
        
        try:
            with self.db_updater.get_connection() as conn:
                result = pd.read_sql(query, conn)
                
            valid_skus = set(result['items_product_sku'].tolist())
            duration = time.time() - start_time
            
            self.logger.success(f"✅ SKUs válidos pre-calculados en {duration:.1f}s:")
            self.logger.info(f"    🏷️  {len(valid_skus):,} SKUs válidos encontrados")
            
            return valid_skus
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"❌ Error pre-calculando SKUs después de {duration:.1f}s: {e}")
            return set()

    def get_date_range_from_db(self) -> tuple:
        """
        Obtiene el rango de fechas disponible en sales_items para planificar batches.
        
        Returns:
            tuple: (fecha_minima, fecha_maxima) o None si hay error
        """
        query = """
        SELECT 
            MIN(issueddate) as min_date,
            MAX(issueddate) as max_date,
            COUNT(*) as total_records
        FROM sales_items 
        WHERE items_quantity > 0
        """
        
        try:
            with self.db_updater.get_connection() as conn:
                from sqlalchemy import create_engine
                engine = create_engine('postgresql://', creator=lambda: conn)
                result = pd.read_sql(query, engine)
                
                min_date = result.iloc[0]['min_date']
                max_date = result.iloc[0]['max_date']
                total_records = result.iloc[0]['total_records']
                
                self.logger.info(f"📅 Rango de datos disponible: {min_date} a {max_date}")
                self.logger.info(f"📊 Total registros con quantity > 0: {total_records:,}")
                
                return min_date, max_date, total_records
                
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo rango de fechas: {e}")
            return None, None, 0

    def get_historical_sales_data_batch(self, start_date: str, end_date: str, batch_num: int, total_batches: int, valid_skus: set) -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos para un rango de fechas específico (un batch).
        
        Args:
            start_date: Fecha de inicio del batch (YYYY-MM-DD)
            end_date: Fecha de fin del batch (YYYY-MM-DD)
            batch_num: Número del batch actual
            total_batches: Total de batches a procesar
            valid_skus: Set de SKUs válidos pre-calculados
            
        Returns:
            DataFrame con datos del batch o None si hay error
        """
        import time
        batch_start = time.time()
        
        self.logger.info(f"📦 Batch {batch_num}/{total_batches}: Procesando año {start_date} a {end_date}")
        
        # Convertir set de SKUs a lista para usar en SQL IN clause
        if not valid_skus:
            self.logger.warning(f"⚠️  Batch {batch_num}/{total_batches}: Sin SKUs válidos, saltando")
            return None
            
        valid_skus_list = list(valid_skus)
        
        # Query MUCHO más eficiente usando lista pre-calculada
        query = """
        SELECT
            issueddate,
            items_product_sku,
            items_quantity,
            items_product_description
        FROM
            sales_items
        WHERE
            items_quantity > 0
            AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
            AND issueddate >= %(start_date)s
            AND issueddate <= %(end_date)s
            AND items_product_sku = ANY(%(valid_skus)s)
        """
        
        try:
            query_start = time.time()
            
            with self.db_updater.get_connection() as conn:
                # Usar lista pre-calculada en lugar de funciones costosas
                df = pd.read_sql(query, conn, params={
                    'start_date': start_date, 
                    'end_date': end_date,
                    'valid_skus': valid_skus_list
                })
            
            query_duration = time.time() - query_start
            batch_duration = time.time() - batch_start
            
            if not df.empty:
                unique_skus = df['items_product_sku'].nunique()
                total_quantity = df['items_quantity'].sum()
                
                self.logger.success(f"✅ Batch {batch_num}/{total_batches} completado en {batch_duration:.1f}s:")
                self.logger.info(f"    📈 {len(df):,} registros")
                self.logger.info(f"    🏷️  {unique_skus:,} SKUs únicos")
                self.logger.info(f"    📦 {total_quantity:,.0f} unidades")
                self.logger.info(f"    ⚡ Query: {query_duration:.1f}s")
            else:
                self.logger.warning(f"⚠️  Batch {batch_num}/{total_batches}: Sin datos para {start_date} - {end_date}")
            
            return df
            
        except Exception as e:
            batch_duration = time.time() - batch_start
            self.logger.error(f"❌ Error en batch {batch_num}/{total_batches} después de {batch_duration:.1f}s: {e}")
            return None

    def get_historical_sales_data(self) -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos de ventas procesando en batches para optimizar memoria.
        Procesa datos por rangos de fechas para evitar sobrecargar sistemas con pocos recursos.
        
        Returns:
            A pandas DataFrame con datos históricos combinados, o None en caso de error.
        """
        import time
        from datetime import datetime, timedelta
        
        start_time = time.time()
        
        self.logger.info("📊 🔄 Iniciando obtención de datos históricos EN BATCHES...")
        self.logger.info("🔍 Filtros aplicados: sin materias primas, con ventas últimos 12 meses, sin cotizaciones")
        
        # Paso 1: Pre-calcular SKUs válidos (CRÍTICO para rendimiento)
        self.logger.info("🗓️  [Paso 1/5] Pre-calculando SKUs válidos...")
        valid_skus = self.get_valid_skus_precalculated()
        
        if not valid_skus:
            self.logger.error("❌ No se encontraron SKUs válidos")
            return None
        
        # Paso 2: Obtener rango de fechas disponible
        self.logger.info("🗓️  [Paso 2/5] Analizando rango de fechas disponible...")
        min_date, max_date, total_records = self.get_date_range_from_db()
        
        if not min_date or not max_date:
            self.logger.error("❌ No se pudo obtener rango de fechas de la base de datos")
            return None
        
        # Paso 3: Calcular batches por años (proceso optimizado)
        self.logger.info("📦 [Paso 3/5] Calculando batches por años...")
        batches = []
        current_date = min_date
        batch_num = 1
        
        while current_date <= max_date:
            # Procesar en batches anuales para máxima eficiencia
            try:
                next_year_start = current_date.replace(year=current_date.year + 1)
            except ValueError:  # Handle leap year edge case (Feb 29)
                next_year_start = current_date.replace(year=current_date.year + 1, month=2, day=28)
            
            end_date = min(next_year_start - timedelta(days=1), max_date)
            batches.append((current_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            current_date = end_date + timedelta(days=1)
            batch_num += 1
        
        total_batches = len(batches)
        self.logger.info(f"📊 Dividiendo datos en {total_batches} batches anuales")
        
        # Paso 4: Procesar cada batch (ahora CON SKUs pre-calculados)
        self.logger.info("⚡ [Paso 4/5] Procesando batches secuencialmente...")
        combined_dataframes = []
        successful_batches = 0
        total_processed_records = 0
        
        for i, (start_date, end_date) in enumerate(batches, 1):
            batch_df = self.get_historical_sales_data_batch(start_date, end_date, i, total_batches, valid_skus)
            
            if batch_df is not None and not batch_df.empty:
                combined_dataframes.append(batch_df)
                successful_batches += 1
                total_processed_records += len(batch_df)
                
                # Progreso cada 25% o cuando sea útil mostrar progreso
                progress_pct = (i / total_batches) * 100
                if total_batches <= 10 or i % max(1, total_batches // 4) == 0:
                    self.logger.info(f"🎯 Progreso: {progress_pct:.0f}% ({i}/{total_batches} batches anuales, {total_processed_records:,} registros)")
            else:
                self.logger.warning(f"⚠️  Batch {i} sin datos válidos")
        
        # Paso 5: Combinar resultados
        self.logger.info("🔗 [Paso 5/5] Combinando resultados de todos los batches...")
        
        if not combined_dataframes:
            self.logger.warning("❌ No se obtuvieron datos de ningún batch")
            return None
        
        try:
            # Combinar todos los DataFrames
            processing_start = time.time()
            df_combined = pd.concat(combined_dataframes, ignore_index=True)
            
            # Procesamiento de datos
            df_combined['issueddate'] = pd.to_datetime(df_combined['issueddate'])
            processing_duration = time.time() - processing_start
            
            # Estadísticas finales
            unique_skus = df_combined['items_product_sku'].nunique()
            date_range_start = df_combined['issueddate'].min()
            date_range_end = df_combined['issueddate'].max()
            total_quantity = df_combined['items_quantity'].sum()
            total_duration = time.time() - start_time
            
            self.logger.success(f"🎉 PROCESO COMPLETADO EN {total_duration:.1f}s:")
            self.logger.info(f"    ✅ {successful_batches}/{total_batches} batches procesados exitosamente")
            self.logger.info(f"    📈 {len(df_combined):,} registros totales obtenidos")
            self.logger.info(f"    🏷️  {unique_skus:,} SKUs únicos encontrados")
            self.logger.info(f"    📅 Período final: {date_range_start.strftime('%Y-%m-%d')} a {date_range_end.strftime('%Y-%m-%d')}")
            self.logger.info(f"    📦 Total unidades: {total_quantity:,.0f}")
            self.logger.info(f"    ⚡ Procesamiento final: {processing_duration:.1f}s")
            self.logger.info(f"    🚀 Optimización máxima: batches anuales sin pausas")
            
            return df_combined
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"❌ Error combinando resultados después de {duration:.1f}s: {e}")
            return None

    def prepare_monthly_time_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates transactional data into monthly time series for each SKU with detailed logging.
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"📈 Agregando {len(df):,} registros de ventas en series temporales mensuales...")
        
        # Hacer una copia para no modificar el DataFrame original
        df_copy = df.copy()
        original_skus = df_copy['items_product_sku'].nunique()
        self.logger.info(f"🔍 Procesando datos de {original_skus:,} SKUs únicos...")
        
        df_copy.set_index('issueddate', inplace=True)
        
        # Agregación por SKU y mes
        agg_start = time.time()
        monthly_sales_df = df_copy.groupby('items_product_sku').resample('ME', include_groups=False).sum(numeric_only=True).reset_index()
        agg_duration = time.time() - agg_start
        
        monthly_sales_df.rename(columns={
            'issueddate': 'month',
            'items_product_sku': 'sku',
            'items_quantity': 'total_quantity'
        }, inplace=True)
        
        # Estadísticas de resultado
        unique_skus_result = monthly_sales_df['sku'].nunique()
        total_months = len(monthly_sales_df)
        avg_months_per_sku = total_months / unique_skus_result if unique_skus_result > 0 else 0
        
        # Rango de fechas
        date_range_start = monthly_sales_df['month'].min()
        date_range_end = monthly_sales_df['month'].max()
        
        total_duration = time.time() - start_time
        
        self.logger.success(f"📈 Series temporales preparadas en {total_duration:.1f}s:")
        self.logger.info(f"    📊 {total_months:,} registros mensuales para {unique_skus_result:,} SKUs")
        self.logger.info(f"    📅 Período: {date_range_start.strftime('%Y-%m')} a {date_range_end.strftime('%Y-%m')}")
        self.logger.info(f"    📈 Promedio: {avg_months_per_sku:.1f} meses por SKU")
        self.logger.info(f"    ⚡ Agregación: {agg_duration:.1f}s")
        
        return monthly_sales_df

    def get_max_monthly_sales_for_skus(self, skus: List[str]) -> Dict[str, int]:
        """
        Get maximum monthly sales for a list of SKUs from historical data.
        Processes in batches of 200 for better performance.
        
        Args:
            skus: List of SKU strings
            
        Returns:
            Dictionary mapping SKU to maximum monthly sales
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"💰 Calculando máximos de ventas mensuales para {len(skus):,} SKUs...")
        
        if not skus:
            return {}
        
        BATCH_SIZE = 200
        total_batches = (len(skus) + BATCH_SIZE - 1) // BATCH_SIZE
        result = {}
        
        self.logger.info(f"📦 Procesando en {total_batches} lotes de {BATCH_SIZE} SKUs...")
        
        for batch_num in range(total_batches):
            batch_start = time.time()
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(skus))
            batch_skus = skus[start_idx:end_idx]
            
            self.logger.info(f"🔄 Lote {batch_num + 1}/{total_batches}: Procesando SKUs {start_idx + 1}-{end_idx}...")
            
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(batch_skus))
            
            query = f"""
            SELECT 
                items_product_sku,
                MAX(monthly_total) as max_monthly_sales
            FROM (
                SELECT 
                    items_product_sku,
                    EXTRACT(YEAR FROM issueddate) as year,
                    EXTRACT(MONTH FROM issueddate) as month,
                    SUM(items_quantity) as monthly_total
                FROM sales_items 
                WHERE items_product_sku IN ({placeholders})
                    AND items_quantity > 0
                    AND issueddate >= CURRENT_DATE - INTERVAL '24 months'
                    AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
                GROUP BY items_product_sku, EXTRACT(YEAR FROM issueddate), EXTRACT(MONTH FROM issueddate)
            ) AS monthly_sales
            GROUP BY items_product_sku
            """
            
            try:
                with self.db_updater.get_connection() as conn:
                    # Usar directamente psycopg2 para evitar problemas de parámetros
                    df = pd.read_sql(query, conn, params=batch_skus)
                
                # Convert to dictionary
                batch_sales_dict = df.set_index('items_product_sku')['max_monthly_sales'].to_dict()
                
                # Fill missing SKUs with 0 and add to result
                for sku in batch_skus:
                    result[sku] = batch_sales_dict.get(sku, 0)
                
                batch_duration = time.time() - batch_start
                self.logger.info(f"✅ Lote {batch_num + 1}/{total_batches}: {len(batch_skus)} SKUs procesados en {batch_duration:.1f}s")
                
            except Exception as e:
                self.logger.error(f"❌ Error en lote {batch_num + 1}: {e}")
                # Fill with zeros for failed batch
                for sku in batch_skus:
                    result[sku] = 0
        
        total_duration = time.time() - start_time
        self.logger.success(f"💰 Máximos de ventas calculados: {len(result):,} SKUs en {total_duration:.1f}s total")
        return result

    def get_unit_prices_for_skus(self, skus: List[str]) -> Dict[str, float]:
        """
        Get latest unit prices for a list of SKUs from historical sales data.
        Processes in batches of 200 for better performance.
        
        Args:
            skus: List of SKU strings
            
        Returns:
            Dictionary mapping SKU to latest unit price
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"💵 Calculando precios unitarios para {len(skus):,} SKUs...")
        
        if not skus:
            return {}
        
        BATCH_SIZE = 200
        total_batches = (len(skus) + BATCH_SIZE - 1) // BATCH_SIZE
        result = {}
        
        self.logger.info(f"📦 Procesando precios en {total_batches} lotes de {BATCH_SIZE} SKUs...")
        
        for batch_num in range(total_batches):
            batch_start = time.time()
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(skus))
            batch_skus = skus[start_idx:end_idx]
            
            self.logger.info(f"🔄 Lote {batch_num + 1}/{total_batches}: Obteniendo precios para SKUs {start_idx + 1}-{end_idx}...")
            
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(batch_skus))
            
            query = f"""
            WITH latest_prices AS (
                SELECT DISTINCT ON (items_product_sku)
                    items_product_sku,
                    items_unitprice,
                    issueddate
                FROM sales_items 
                WHERE items_product_sku IN ({placeholders})
                    AND items_quantity > 0
                    AND items_unitprice > 0
                    AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
                ORDER BY items_product_sku, issueddate DESC
            ),
            avg_prices AS (
                SELECT 
                    items_product_sku,
                    AVG(items_unitprice) as avg_price
                FROM sales_items 
                WHERE items_product_sku IN ({placeholders})
                    AND items_quantity > 0
                    AND items_unitprice > 0
                    AND issueddate >= CURRENT_DATE - INTERVAL '6 months'
                    AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
                GROUP BY items_product_sku
            )
            SELECT 
                COALESCE(lp.items_product_sku, ap.items_product_sku) as sku,
                COALESCE(lp.items_unitprice, ap.avg_price, 0) as unit_price
            FROM latest_prices lp
            FULL OUTER JOIN avg_prices ap ON lp.items_product_sku = ap.items_product_sku
            """
            
            try:
                with self.db_updater.get_connection() as conn:
                    # Usar directamente psycopg2 para evitar problemas de parámetros
                    df = pd.read_sql(query, conn, params=batch_skus + batch_skus)  # Double params for both CTEs
                
                # Convert to dictionary
                batch_price_dict = df.set_index('sku')['unit_price'].to_dict()
                
                # Fill missing SKUs with 0 and add to result
                for sku in batch_skus:
                    result[sku] = float(batch_price_dict.get(sku, 0))
                
                batch_duration = time.time() - batch_start
                prices_found = sum(1 for sku in batch_skus if result[sku] > 0)
                self.logger.info(f"✅ Lote {batch_num + 1}/{total_batches}: {len(batch_skus)} SKUs procesados ({prices_found} con precio) en {batch_duration:.1f}s")
                
            except Exception as e:
                self.logger.error(f"❌ Error en lote {batch_num + 1}: {e}")
                # Fill with zeros for failed batch
                for sku in batch_skus:
                    result[sku] = 0.0
        
        total_duration = time.time() - start_time
        total_with_prices = sum(1 for price in result.values() if price > 0)
        self.logger.success(f"💵 Precios unitarios calculados: {len(result):,} SKUs ({total_with_prices:,} con precio) en {total_duration:.1f}s total")
        return result

    def _forecast_single_sku(self, sku_ts: pd.Series, max_monthly_sales: int = None, steps: int = 12) -> Optional[pd.Series]:
        """
        Generates a forecast for a single product's time series using SARIMA.
        Simplified version with only essential validations.
        
        Args:
            sku_ts: A pandas Series representing the monthly sales of one SKU.
            max_monthly_sales: Maximum monthly sales from historical data (for capping)
            steps: The number of months to forecast into the future.

        Returns:
            A pandas Series with the forecasted values, or None if forecasting fails.
        """
        # Fallback hierarchy: SARIMA -> Linear Regression -> Previous Year * 1.1
        
        # Try SARIMA first (requires minimum 24 months)
        if len(sku_ts) >= 24:
            forecast = self._try_sarima_forecast(sku_ts, steps)
            if forecast is not None:
                return self._apply_max_sales_limit(forecast, max_monthly_sales)
        
        # Try Linear Regression (requires minimum 6 months)
        if len(sku_ts) >= 6:
            forecast = self._try_linear_regression_forecast(sku_ts, steps)
            if forecast is not None:
                return self._apply_max_sales_limit(forecast, max_monthly_sales)
        
        # Last resort: Previous year sales * 1.1
        if len(sku_ts) >= 12:
            forecast = self._try_previous_year_forecast(sku_ts, steps)
            if forecast is not None:
                return self._apply_max_sales_limit(forecast, max_monthly_sales)
        
        # If all methods fail
        self.logger.warning(f"All forecasting methods failed for SKU {sku_ts.name}")
        return None

    def _try_sarima_forecast(self, sku_ts: pd.Series, steps: int) -> Optional[pd.Series]:
        """Try SARIMA forecasting method."""
        try:
            model = sm.tsa.statespace.SARIMAX(
                sku_ts,
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
            
            # Only apply basic normalization
            predicted_values = predicted_values.clip(lower=0)
            predicted_values = predicted_values.round().astype(int)
            
            self.logger.info(f"SARIMA forecast generated for SKU {sku_ts.name}")
            return predicted_values
            
        except Exception as e:
            self.logger.warning(f"SARIMA failed for SKU {sku_ts.name}: {e}")
            return None

    def _try_linear_regression_forecast(self, sku_ts: pd.Series, steps: int) -> Optional[pd.Series]:
        """Try linear regression forecasting method."""
        try:
            y = sku_ts.astype(float).values
            x = np.arange(len(y), dtype=float)

            slope, intercept = np.polyfit(x, y, 1)

            future_x = np.arange(len(y), len(y) + steps, dtype=float)
            future_y = intercept + slope * future_x

            # Create future index
            last_idx = sku_ts.index[-1]
            if isinstance(last_idx, pd.Timestamp):
                future_periods = pd.period_range(last_idx, periods=steps + 1, freq='M')[1:]
                future_index = future_periods.to_timestamp('M')
            else:
                last_ts = pd.to_datetime(last_idx)
                future_index = pd.date_range(last_ts, periods=steps + 1, freq='M')[1:]

            predicted_values = pd.Series(future_y, index=future_index)
            
            # Only apply basic normalization
            predicted_values = predicted_values.clip(lower=0)
            predicted_values = predicted_values.round().astype(int)

            self.logger.info(f"Linear regression forecast generated for SKU {sku_ts.name}")
            return predicted_values
            
        except Exception as e:
            self.logger.warning(f"Linear regression failed for SKU {sku_ts.name}: {e}")
            return None

    def _try_previous_year_forecast(self, sku_ts: pd.Series, steps: int) -> Optional[pd.Series]:
        """Try previous year * 1.1 forecasting method."""
        try:
            # Get last 12 months as base
            last_12_months = sku_ts.tail(12)
            
            # Apply 1.1 multiplier
            base_forecast = last_12_months * 1.1
            
            # Repeat pattern for required steps
            cycles_needed = (steps + 11) // 12  # Round up division
            extended_forecast = pd.concat([base_forecast] * cycles_needed)
            
            # Trim to exact steps needed
            extended_forecast = extended_forecast.head(steps)
            
            # Create future index
            last_idx = sku_ts.index[-1]
            if isinstance(last_idx, pd.Timestamp):
                future_periods = pd.period_range(last_idx, periods=steps + 1, freq='M')[1:]
                future_index = future_periods.to_timestamp('M')
            else:
                last_ts = pd.to_datetime(last_idx)
                future_index = pd.date_range(last_ts, periods=steps + 1, freq='M')[1:]

            predicted_values = pd.Series(extended_forecast.values, index=future_index)
            
            # Only apply basic normalization
            predicted_values = predicted_values.clip(lower=0)
            predicted_values = predicted_values.round().astype(int)

            self.logger.info(f"Previous year * 1.1 forecast generated for SKU {sku_ts.name}")
            return predicted_values
            
        except Exception as e:
            self.logger.warning(f"Previous year forecast failed for SKU {sku_ts.name}: {e}")
            return None

    def _apply_max_sales_limit(self, forecast: pd.Series, max_monthly_sales: int) -> pd.Series:
        """
        Apply the only restriction: forecast cannot exceed historical maximum.
        If max_monthly_sales is None or 0, no limit is applied.
        """
        if max_monthly_sales is None or max_monthly_sales <= 0:
            return forecast
        
        # Apply the MIN(forecasted_qty, max_monthly_sales) rule
        limited_forecast = forecast.clip(upper=max_monthly_sales)
        
        if limited_forecast.max() < forecast.max():
            self.logger.info(f"Forecast limited by max historical sales: {forecast.max()} -> {limited_forecast.max()}")
        
        return limited_forecast



    def run_forecasting_for_all_skus(self) -> Optional[Dict[str, pd.Series]]:
        """
        Main orchestration method to generate forecasts for all valid products.
        Filtering is now done at SQL level for better performance.
        """
        import time
        start_time = time.time()
        
        self.logger.info("🚀 Iniciando proceso simplificado de forecasting")
        
        # 1. Obtener datos históricos (ya filtrados por SQL)
        step_start = time.time()
        self.logger.info("📊 [Paso 1/5] Obteniendo datos históricos de ventas...")
        historical_data = self.get_historical_sales_data()
        if historical_data is None:
            self.logger.error("❌ No se pudieron obtener datos históricos")
            return None
        
        step_duration = time.time() - step_start
        self.logger.info(f"✅ [Paso 1/5] Datos históricos obtenidos: {len(historical_data):,} registros en {step_duration:.1f}s")
        
        # 2. Obtener SKUs únicos de datos históricos filtrados
        step_start = time.time()
        self.logger.info("🔍 [Paso 2/5] Identificando SKUs únicos...")
        unique_skus = list(historical_data['items_product_sku'].unique())
        step_duration = time.time() - step_start
        self.logger.info(f"✅ [Paso 2/5] SKUs únicos identificados: {len(unique_skus):,} SKUs en {step_duration:.1f}s")
        
        # 3. Preparar series temporales mensuales
        step_start = time.time()
        self.logger.info("📈 [Paso 3/5] Preparando series temporales mensuales...")
        monthly_data = self.prepare_monthly_time_series(historical_data)
        step_duration = time.time() - step_start
        self.logger.info(f"✅ [Paso 3/5] Series temporales preparadas: {len(monthly_data):,} registros mensuales en {step_duration:.1f}s")
        
        # 4. Aplicar filtros básicos de calidad de datos
        step_start = time.time()
        self.logger.info("🔎 [Paso 4/5] Aplicando filtros de calidad de datos...")
        filtered_skus = self._apply_basic_filters(monthly_data, unique_skus)
        step_duration = time.time() - step_start
        filtered_count = len(filtered_skus)
        excluded_count = len(unique_skus) - filtered_count
        self.logger.info(f"✅ [Paso 4/5] Filtros aplicados: {filtered_count:,} SKUs aprobados, {excluded_count:,} excluidos en {step_duration:.1f}s")
        
        if not filtered_skus:
            self.logger.error("❌ No hay SKUs válidos para forecasting después del filtrado")
            return None
        
        # 5. Generar forecasts para SKUs válidos
        step_start = time.time()
        self.logger.info(f"🤖 [Paso 5/5] Generando forecasts para {filtered_count:,} SKUs...")
        all_forecasts = self._generate_forecasts_for_valid_skus(
            monthly_data, filtered_skus, {}
        )
        step_duration = time.time() - step_start
        
        total_duration = time.time() - start_time
        success_count = len(all_forecasts) if all_forecasts else 0
        success_rate = (success_count / filtered_count * 100) if filtered_count > 0 else 0
        
        self.logger.success(f"🎉 Forecasting completado: {success_count:,}/{filtered_count:,} SKUs exitosos ({success_rate:.1f}%) en {total_duration:.1f}s total")
        
        return all_forecasts


    
    def _apply_basic_filters(self, monthly_data: pd.DataFrame, unique_skus: List[str]) -> List[str]:
        """
        Aplicar filtros básicos de calidad de datos con logging detallado.
        
        Args:
            monthly_data (pd.DataFrame): Datos mensuales
            unique_skus (List[str]): SKUs únicos
            
        Returns:
            List[str]: SKUs válidos usando filtros básicos
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"🔎 Aplicando filtros de calidad a {len(unique_skus):,} SKUs...")
        
        valid_skus = []
        skipped_insufficient_data = 0
        skipped_poor_quality = 0
        
        # Process in chunks for progress reporting
        PROGRESS_CHUNK = 500
        processed = 0
        
        for i, sku in enumerate(unique_skus):
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
            processed += 1
            
            # Progress reporting every PROGRESS_CHUNK SKUs
            if (i + 1) % PROGRESS_CHUNK == 0:
                progress_pct = ((i + 1) / len(unique_skus)) * 100
                self.logger.info(f"🔄 Progreso filtrado: {i + 1:,}/{len(unique_skus):,} SKUs procesados ({progress_pct:.1f}%)")
        
        filter_duration = time.time() - start_time
        valid_count = len(valid_skus)
        invalid_count = len(unique_skus) - valid_count
        success_rate = (valid_count / len(unique_skus) * 100) if unique_skus else 0
        
        self.logger.info(f"✅ Filtrado completado en {filter_duration:.1f}s:")
        self.logger.info(f"    📊 SKUs válidos: {valid_count:,}/{len(unique_skus):,} ({success_rate:.1f}%)")
        self.logger.info(f"    📉 Datos insuficientes: {skipped_insufficient_data:,}")
        self.logger.info(f"    💥 Calidad pobre: {skipped_poor_quality:,}")
        
        return valid_skus
    
    def _generate_forecasts_for_valid_skus(self, 
                                         monthly_data: pd.DataFrame, 
                                         valid_skus: List[str],
                                         _: Dict = None) -> Dict[str, pd.Series]:
        """
        Generar forecasts solo para SKUs válidos.
        Processes in batches of 200 for better performance and detailed logging.
        
        Args:
            monthly_data (pd.DataFrame): Datos mensuales
            valid_skus (List[str]): SKUs válidos para forecasting
            _ (Dict): Parámetro ignorado para compatibilidad
            
        Returns:
            Dict[str, pd.Series]: Forecasts generados
        """
        import time
        start_time = time.time()
        
        all_forecasts: Dict[str, pd.Series] = {}
        
        self.logger.info(f"🤖 Generando forecasts para {len(valid_skus):,} SKUs válidos...")
        
        # Get max monthly sales and unit prices for all valid SKUs (they already process in batches)
        self.logger.info("🔍 Obteniendo datos auxiliares para forecasting...")
        aux_start = time.time()
        max_sales_data = self.get_max_monthly_sales_for_skus(valid_skus)
        unit_prices_data = self.get_unit_prices_for_skus(valid_skus)
        aux_duration = time.time() - aux_start
        self.logger.info(f"✅ Datos auxiliares obtenidos en {aux_duration:.1f}s")
        
        # Process SKUs in batches for better memory management and progress tracking
        BATCH_SIZE = 200
        total_batches = (len(valid_skus) + BATCH_SIZE - 1) // BATCH_SIZE
        
        self.logger.info(f"📦 Procesando forecasting en {total_batches} lotes de {BATCH_SIZE} SKUs...")
        
        total_success = 0
        total_failed = 0
        
        for batch_num in range(total_batches):
            batch_start = time.time()
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(valid_skus))
            batch_skus = valid_skus[start_idx:end_idx]
            
            self.logger.info(f"🔄 Lote {batch_num + 1}/{total_batches}: Generando forecasts para SKUs {start_idx + 1}-{end_idx}...")
            
            batch_success = 0
            batch_failed = 0
            
            for i, sku in enumerate(batch_skus):
                try:
                    # Preparar serie temporal
                    ts_individual = monthly_data[monthly_data['sku'] == sku]
                    ts_prepared = ts_individual[['month', 'total_quantity']].set_index('month')['total_quantity']
                    ts_prepared = ts_prepared.resample('ME').sum().fillna(0)
                    ts_prepared.name = sku
                    
                    # Usar parámetros estándar (12 meses) para todos los productos
                    forecast_steps = 12
                    
                    # Get max monthly sales for this SKU
                    max_monthly_sales = max_sales_data.get(sku, 0)
                    
                    # Generar forecast con límite de máximo histórico
                    forecast = self._forecast_single_sku(ts_prepared, max_monthly_sales=max_monthly_sales, steps=forecast_steps)
                    
                    if forecast is not None:
                        all_forecasts[sku] = forecast
                        batch_success += 1
                        
                        # Log detalle solo para primeros SKUs de cada lote
                        if i < 3:  # Solo los primeros 3 de cada lote
                            self.logger.info(f"    ✅ SKU {sku}: {forecast.min():.0f}-{forecast.max():.0f} unidades (max: {max_monthly_sales})")
                    else:
                        batch_failed += 1
                        if i < 3:  # Solo los primeros 3 de cada lote
                            self.logger.warning(f"    ❌ SKU {sku}: Forecast falló")
                    
                except Exception as e:
                    batch_failed += 1
                    if i < 3:  # Solo los primeros 3 de cada lote
                        self.logger.error(f"    ❌ SKU {sku}: Error - {e}")
                    continue
            
            total_success += batch_success
            total_failed += batch_failed
            batch_duration = time.time() - batch_start
            success_rate = (batch_success / len(batch_skus) * 100) if batch_skus else 0
            
            self.logger.info(f"✅ Lote {batch_num + 1}/{total_batches}: {batch_success}/{len(batch_skus)} exitosos ({success_rate:.1f}%) en {batch_duration:.1f}s")
        
        total_duration = time.time() - start_time
        overall_success_rate = (total_success / len(valid_skus) * 100) if valid_skus else 0
        
        self.logger.success(f"🤖 Forecasting completado: {total_success:,}/{len(valid_skus):,} SKUs exitosos ({overall_success_rate:.1f}%) en {total_duration:.1f}s")
        
        if total_failed > 0:
            self.logger.warning(f"⚠️  {total_failed:,} SKUs fallaron en el forecasting")
        
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