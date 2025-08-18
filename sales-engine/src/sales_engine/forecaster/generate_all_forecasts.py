#!/usr/bin/env python3
"""
Generador de Forecasts para Todos los Productos (con Limpieza Integrada)

Este script genera proyecciones SARIMA para todos los SKUs, 
limpia valores extremos y exporta tanto versiones originales 
como limpias para análisis posterior.
"""

import sys
import os
import argparse
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
import structlog

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Crear directorio de forecasts si no existe
FORECASTS_DIR = Path("data/forecasts")
FORECASTS_DIR.mkdir(parents=True, exist_ok=True)

# Imports
from sales_engine.forecaster import SalesForecaster
from config_manager import secrets

# Configurar logger
logger = structlog.get_logger(__name__)


class DatabaseForecastUpdater:
    """
    Maneja la inserción/actualización de forecasts en la base de datos.
    Sigue el patrón de DatabaseUpdater del sales-engine.
    """
    
    def __init__(self):
        """Inicializar el updater de forecasts."""
        self.config = secrets
        self.logger = logger.bind(component="forecast_database_updater")
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        
        self.logger.info(
            "DatabaseForecastUpdater inicializado",
            environment=self.config.ENVIRONMENT
        )
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Obtener parámetros de conexión de la base de datos."""
        try:
            db_config = self.config.get_database_config()
            db_config['port'] = int(db_config['port'])
            return db_config
        except Exception as e:
            self.logger.error("Error en configuración de base de datos", error=str(e))
            raise Exception("La configuración de base de datos está incompleta.") from e
    
    def _setup_connection_pool(self):
        """Inicializar pool de conexiones de base de datos."""
        if self._connection_pool:
            return
            
        try:
            params = self._get_connection_params()
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2, maxconn=10, connect_timeout=30, **params
            )
            self.logger.info(
                "Pool de conexiones de base de datos creado", 
                host=params.get('host'), 
                database=params.get('database')
            )
        except Exception as e:
            self.logger.error("Error al crear pool de conexiones", error=str(e))
            raise Exception("Error al crear pool de conexiones.") from e
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexiones pooled de base de datos."""
        if not self._connection_pool:
            self._setup_connection_pool()

        conn = None
        try:
            conn = self._connection_pool.getconn()
            yield conn
            conn.commit()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            self.logger.error("Transacción de base de datos falló", error=str(e))
            raise Exception("Transacción de base de datos falló.") from e
        finally:
            if conn:
                self._connection_pool.putconn(conn)
    
    def _ensure_forecast_table_exists(self):
        """Crear tabla forecast si no existe."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS forecast (
            sku VARCHAR(50) NOT NULL,
            forecast_date DATE NOT NULL,
            forecasted_quantity INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            month_name VARCHAR(20) NOT NULL,
            quarter VARCHAR(5) NOT NULL,
            week_of_year INTEGER NOT NULL,
            total_forecast_12_months INTEGER,
            avg_monthly_forecast DECIMAL(10,2),
            std_dev DECIMAL(10,2),
            min_monthly_forecast INTEGER,
            max_monthly_forecast INTEGER,
            months_forecasted INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (sku, forecast_date)
        );
        """
        
        # Crear función trigger para updated_at
        create_trigger_function_sql = """
        CREATE OR REPLACE FUNCTION update_forecast_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
        
        # Crear trigger
        create_trigger_sql = """
        DROP TRIGGER IF EXISTS update_forecast_updated_at ON forecast;
        CREATE TRIGGER update_forecast_updated_at
            BEFORE UPDATE ON forecast
            FOR EACH ROW EXECUTE FUNCTION update_forecast_updated_at_column();
        """
        
        # Crear índices
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_forecast_sku ON forecast (sku);",
            "CREATE INDEX IF NOT EXISTS idx_forecast_date ON forecast (forecast_date);",
            "CREATE INDEX IF NOT EXISTS idx_forecast_created_at ON forecast (created_at);",
            "CREATE INDEX IF NOT EXISTS idx_forecast_updated_at ON forecast (updated_at);"
        ]
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Crear tabla
                    cursor.execute(create_table_sql)
                    self.logger.info("Tabla forecast verificada/creada")
                    
                    # Crear función trigger
                    cursor.execute(create_trigger_function_sql)
                    
                    # Crear trigger
                    cursor.execute(create_trigger_sql)
                    
                    # Crear índices
                    for index_sql in create_indexes_sql:
                        cursor.execute(index_sql)
                    
                    self.logger.info("Tabla forecast y estructuras auxiliares creadas exitosamente")
                    
        except Exception as e:
            self.logger.error("Error creando tabla forecast", error=str(e))
            raise Exception(f"Error creando tabla forecast: {str(e)}") from e
    
    def upsert_forecasts(self, df_with_stats: pd.DataFrame) -> Dict[str, int]:
        """
        DEPRECATED: Insertar o actualizar forecasts en la base de datos usando UPSERT.
        Esta función mantiene compatibilidad con la estructura antigua.
        Para nuevos desarrollos, usar upsert_unified_forecasts().
        
        Args:
            df_with_stats: DataFrame con forecasts y estadísticas
            
        Returns:
            Dict con contadores de registros insertados/actualizados
        """
        self._ensure_forecast_table_exists()
        
        upsert_sql = """
        INSERT INTO forecast (
            sku, forecast_date, forecasted_quantity, year, month, month_name,
            quarter, week_of_year, total_forecast_12_months, avg_monthly_forecast,
            std_dev, min_monthly_forecast, max_monthly_forecast, months_forecasted
        ) VALUES (
            %(sku)s, %(forecast_date)s, %(forecasted_quantity)s, %(year)s, %(month)s,
            %(month_name)s, %(quarter)s, %(week_of_year)s, %(total_forecast_12_months)s,
            %(avg_monthly_forecast)s, %(std_dev)s, %(min_monthly_forecast)s,
            %(max_monthly_forecast)s, %(months_forecasted)s
        )
        ON CONFLICT (sku, forecast_date) 
        DO UPDATE SET
            forecasted_quantity = EXCLUDED.forecasted_quantity,
            year = EXCLUDED.year,
            month = EXCLUDED.month,
            month_name = EXCLUDED.month_name,
            quarter = EXCLUDED.quarter,
            week_of_year = EXCLUDED.week_of_year,
            total_forecast_12_months = EXCLUDED.total_forecast_12_months,
            avg_monthly_forecast = EXCLUDED.avg_monthly_forecast,
            std_dev = EXCLUDED.std_dev,
            min_monthly_forecast = EXCLUDED.min_monthly_forecast,
            max_monthly_forecast = EXCLUDED.max_monthly_forecast,
            months_forecasted = EXCLUDED.months_forecasted,
            updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Convertir DataFrame a lista de diccionarios con tipos Python nativos seguros
                    import numpy as np
                    
                    def safe_convert(value, target_type):
                        """Convierte valores numpy/pandas a tipos Python nativos de forma segura."""
                        # Manejar valores nulos/NaN
                        if pd.isna(value) or value is None:
                            if target_type == str:
                                return ""
                            elif target_type in (int, float):
                                return target_type(0)
                            return target_type()
                        
                        # Conversión agresiva de tipos NumPy usando .item()
                        if hasattr(value, 'item'):  # Cualquier tipo numpy
                            try:
                                python_value = value.item()  # Extrae valor Python nativo
                                return target_type(python_value)
                            except (ValueError, OverflowError):
                                # Fallback para valores que no caben en el tipo objetivo
                                if target_type == int:
                                    return int(float(value))  # Convertir via float primero
                                return target_type(value)
                        
                        # Conversión directa para tipos Python nativos
                        try:
                            return target_type(value)
                        except (ValueError, TypeError):
                            # Último fallback
                            if target_type == str:
                                return str(value)
                            elif target_type in (int, float):
                                return target_type(0)
                            return target_type()
                    
                    # Convertir DataFrame a lista de diccionarios con tipos seguros
                    records = []
                    for _, row in df_with_stats.iterrows():
                        # Determinar tipos objetivo según las columnas disponibles
                        record = {}
                        for col_name, value in row.items():
                            if col_name in ['sku', 'month_name']:
                                record[col_name] = safe_convert(value, str)
                            elif col_name in ['year', 'month', 'quarter', 'week_of_year', 'months_forecasted', 'forecasted_quantity', 'min_monthly_forecast', 'max_monthly_forecast']:
                                record[col_name] = safe_convert(value, int)
                            elif col_name in ['total_forecast_12_months', 'avg_monthly_forecast', 'std_dev']:
                                record[col_name] = safe_convert(value, float)
                            elif col_name == 'forecast_date':
                                record[col_name] = value  # Mantener como fecha
                            else:
                                # Para cualquier campo no especificado, convertir según el tipo actual
                                if isinstance(value, (int, np.integer)):
                                    record[col_name] = safe_convert(value, int)
                                elif isinstance(value, (float, np.floating)):
                                    record[col_name] = safe_convert(value, float)
                                else:
                                    record[col_name] = safe_convert(value, str)
                        records.append(record)
                    
                    # Ejecutar upserts en lotes
                    batch_size = 1000
                    total_processed = 0
                    
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i + batch_size]
                        
                        # Ejecutar batch
                        psycopg2.extras.execute_batch(
                            cursor, upsert_sql, batch, page_size=batch_size
                        )
                        
                        total_processed += len(batch)
                        
                        self.logger.info(
                            f"Batch procesado",
                            processed=total_processed,
                            total=len(records),
                            batch_size=len(batch)
                        )
                    
                    # Obtener estadísticas finales
                    cursor.execute("SELECT COUNT(*) FROM forecast")
                    total_records = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(DISTINCT sku) FROM forecast")
                    unique_skus = cursor.fetchone()[0]
                    
                    result = {
                        'total_processed': total_processed,
                        'total_records_in_db': total_records,
                        'unique_skus_in_db': unique_skus
                    }
                    
                    self.logger.info(
                        "Forecasts guardados en base de datos exitosamente",
                        **result
                    )
                    
                    return result
                    
        except Exception as e:
            self.logger.error("Error guardando forecasts en base de datos", error=str(e))
            raise Exception(f"Error guardando forecasts: {str(e)}") from e

    def upsert_unified_forecasts(self, unified_df: pd.DataFrame) -> Dict[str, int]:
        """
        Insertar o actualizar forecasts unificados en la nueva estructura de tabla.
        
        Args:
            unified_df: DataFrame con estructura unificada (sku, year, month, max_monthly_sales, 
                       current_stock, forecasted_qty, required_production, unit_price, priority)
            
        Returns:
            Dict con contadores de registros insertados/actualizados
        """
        upsert_sql = """
        INSERT INTO forecast (
            sku, year, month, max_monthly_sales, current_stock, 
            forecasted_qty, required_production, unit_price, priority
        ) VALUES (
            %(sku)s, %(year)s, %(month)s, %(max_monthly_sales)s, %(current_stock)s,
            %(forecasted_qty)s, %(required_production)s, %(unit_price)s, %(priority)s
        )
        ON CONFLICT (sku, year, month) 
        DO UPDATE SET
            max_monthly_sales = EXCLUDED.max_monthly_sales,
            current_stock = EXCLUDED.current_stock,
            forecasted_qty = EXCLUDED.forecasted_qty,
            required_production = EXCLUDED.required_production,
            unit_price = EXCLUDED.unit_price,
            priority = EXCLUDED.priority,
            updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Convertir DataFrame a lista de diccionarios con tipos Python nativos seguros
                    import numpy as np
                    
                    def safe_convert(value, target_type):
                        """Convierte valores numpy/pandas a tipos Python nativos de forma segura."""
                        # Manejar valores nulos/NaN
                        if pd.isna(value) or value is None:
                            if target_type == str:
                                return ""
                            elif target_type in (int, float):
                                return target_type(0)
                            return target_type()
                        
                        # Conversión agresiva de tipos NumPy usando .item()
                        if hasattr(value, 'item'):  # Cualquier tipo numpy
                            try:
                                python_value = value.item()  # Extrae valor Python nativo
                                return target_type(python_value)
                            except (ValueError, OverflowError):
                                # Fallback para valores que no caben en el tipo objetivo
                                if target_type == int:
                                    return int(float(value))  # Convertir via float primero
                                return target_type(value)
                        
                        # Conversión directa para tipos Python nativos
                        try:
                            return target_type(value)
                        except (ValueError, TypeError):
                            # Último fallback
                            if target_type == str:
                                return str(value)
                            elif target_type in (int, float):
                                return target_type(0)
                            return target_type()
                    
                    records = []
                    conversion_debug = {}  # Para debug de tipos
                    
                    for i, (_, row) in enumerate(unified_df.iterrows()):
                        # Debug de tipos en la primera fila
                        if i == 0:
                            for col in row.index:
                                conversion_debug[col] = type(row[col]).__name__
                        
                        record = {
                            'sku': safe_convert(row['sku'], str),
                            'year': safe_convert(row['year'], int),
                            'month': safe_convert(row['month'], int),
                            'max_monthly_sales': safe_convert(row['max_monthly_sales'], float),  # Cambiar a float
                            'current_stock': safe_convert(row['current_stock'], float),
                            'forecasted_qty': safe_convert(row['forecasted_qty'], int),
                            'required_production': safe_convert(row['required_production'], int),
                            'unit_price': safe_convert(row['unit_price'], float),
                            'priority': safe_convert(row['priority'], str)
                        }
                        records.append(record)
                    
                    # Log de tipos detectados
                    if conversion_debug:
                        self.logger.info("Tipos detectados en DataFrame:", **conversion_debug)
                    
                    # Ejecutar upserts en lotes
                    batch_size = 1000
                    total_processed = 0
                    
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i + batch_size]
                        
                        # Ejecutar batch
                        psycopg2.extras.execute_batch(
                            cursor, upsert_sql, batch, page_size=batch_size
                        )
                        
                        total_processed += len(batch)
                        
                        self.logger.info(
                            f"Batch unificado procesado",
                            processed=total_processed,
                            total=len(records),
                            batch_size=len(batch)
                        )
                    
                    # Obtener estadísticas finales de la nueva estructura
                    cursor.execute("SELECT COUNT(*) FROM forecast")
                    total_records = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(DISTINCT sku) FROM forecast")
                    unique_skus = cursor.fetchone()[0]
                    
                    # Estadísticas por prioridad
                    cursor.execute("""
                        SELECT priority, COUNT(*) as count, SUM(required_production) as total_production
                        FROM forecast 
                        WHERE year = %s AND month = %s
                        GROUP BY priority 
                        ORDER BY 
                            CASE priority 
                                WHEN 'CRITICO' THEN 1 
                                WHEN 'ALTA' THEN 2 
                                WHEN 'MEDIA' THEN 3 
                                WHEN 'BAJA' THEN 4 
                            END
                    """, (safe_convert(unified_df['year'].iloc[0], int), safe_convert(unified_df['month'].iloc[0], int)))
                    
                    priority_stats = cursor.fetchall()
                    
                    result = {
                        'total_processed': total_processed,
                        'total_records_in_db': total_records,
                        'unique_skus_in_db': unique_skus,
                        'priority_breakdown': [
                            {'priority': row[0], 'count': row[1], 'total_production': float(row[2] or 0)} 
                            for row in priority_stats
                        ]
                    }
                    
                    self.logger.info(
                        "Forecasts unificados guardados exitosamente",
                        **{k: v for k, v in result.items() if k != 'priority_breakdown'}
                    )
                    
                    # Log priority breakdown
                    for priority_info in result['priority_breakdown']:
                        self.logger.info(
                            f"Prioridad {priority_info['priority']}",
                            count=priority_info['count'],
                            total_production=priority_info['total_production']
                        )
                    
                    return result
                    
        except Exception as e:
            self.logger.error("Error guardando forecasts unificados", error=str(e))
            raise Exception(f"Error guardando forecasts unificados: {str(e)}") from e


def generate_all_forecasts():
    """Generar forecasts para todos los productos."""
    
    print("🚀 Generando Forecasts para Todos los Productos")
    print("=" * 60)
    
    try:
        # Habilitar validación mejorada de ciclo de vida
        forecaster = SalesForecaster(enable_lifecycle_validation=True)
        print("📊 Iniciando proceso de forecasting para todos los SKUs (con validación de ciclo de vida mejorada)...")
        # Generar forecasts para todos los productos
        all_forecasts = forecaster.run_forecasting_for_all_skus()
        if not all_forecasts:
            print("❌ No se generaron forecasts")
            return None
        print(f"✅ Forecasts generados para {len(all_forecasts)} productos")
        return all_forecasts
            
    except Exception as e:
        print(f"❌ Error generando forecasts: {str(e)}")
        return None

def convert_to_dataframe(forecasts_dict):
    """Convertir diccionario de forecasts a DataFrame estructurado."""
    
    print("\n🔄 Convirtiendo forecasts a DataFrame...")
    
    # Lista para almacenar todas las filas
    forecast_rows = []
    
    for sku, forecast_series in forecasts_dict.items():
        print(f"   📦 Procesando SKU: {sku}")
        
        for date, quantity in forecast_series.items():
            forecast_rows.append({
                'sku': sku,
                'forecast_date': date,
                'forecasted_quantity': int(quantity),
                'year': date.year,
                'month': date.month,
                'month_name': date.strftime('%B'),
                'quarter': f"Q{((date.month-1)//3)+1}",
                'week_of_year': date.isocalendar()[1]
            })
    
    # Crear DataFrame
    df = pd.DataFrame(forecast_rows)
    
    # Ordenar por SKU y fecha
    df = df.sort_values(['sku', 'forecast_date']).reset_index(drop=True)
    
    print(f"✅ DataFrame creado con {len(df)} registros")
    print(f"   📦 SKUs únicos: {df['sku'].nunique()}")
    print(f"   📅 Período: {df['forecast_date'].min()} a {df['forecast_date'].max()}")
    
    return df

def add_summary_statistics(df):
    """Agregar estadísticas de resumen por SKU."""
    
    print("\n📊 Calculando estadísticas de resumen...")
    
    # Estadísticas por SKU
    sku_stats = df.groupby('sku')['forecasted_quantity'].agg([
        'sum', 'mean', 'std', 'min', 'max', 'count'
    ]).round(2)
    
    sku_stats.columns = [
        'total_forecast_12_months',
        'avg_monthly_forecast', 
        'std_dev',
        'min_monthly_forecast',
        'max_monthly_forecast',
        'months_forecasted'
    ]
    
    # Resetear índice para tener SKU como columna
    sku_stats = sku_stats.reset_index()
    
    # Agregar estadísticas al DataFrame principal
    df_with_stats = df.merge(sku_stats, on='sku', how='left')
    
    print(f"✅ Estadísticas agregadas para {len(sku_stats)} SKUs")
    
    return df_with_stats, sku_stats

def export_to_csv(df, sku_stats):
    """Exportar DataFrames a archivos CSV (versión original)."""
    
    print("\n💾 Exportando archivos originales...")
    
    # Fecha para el nombre del archivo
    today = date.today().strftime('%Y%m%d')
    
    # 1. Archivo principal con todos los forecasts
    main_filename = f"forecasts_all_products_{today}.csv"
    main_filepath = FORECASTS_DIR / main_filename
    df.to_csv(main_filepath, index=False)
    print(f"📁 Forecast detallado guardado: {main_filepath}")
    print(f"   📊 Registros: {len(df):,}")
    print(f"   📋 Columnas: {list(df.columns)}")
    
    # 2. Archivo de resumen por SKU
    summary_filename = f"forecast_summary_by_sku_{today}.csv"
    summary_filepath = FORECASTS_DIR / summary_filename
    sku_stats.to_csv(summary_filepath, index=False)
    print(f"📁 Resumen por SKU guardado: {summary_filepath}")
    print(f"   📊 SKUs: {len(sku_stats):,}")
    print(f"   📋 Columnas: {list(sku_stats.columns)}")
    
    # 3. Archivo pivoteado (SKUs como columnas, fechas como filas)
    pivot_df = df.pivot(index='forecast_date', columns='sku', values='forecasted_quantity')
    pivot_filename = f"forecasts_pivot_table_{today}.csv"
    pivot_filepath = FORECASTS_DIR / pivot_filename
    pivot_df.to_csv(pivot_filepath)
    print(f"📁 Tabla pivoteada guardada: {pivot_filepath}")
    print(f"   📅 Fechas: {len(pivot_df)}")
    print(f"   📦 SKUs: {len(pivot_df.columns)}")
    
    return {
        'main_file': str(main_filepath),
        'summary_file': str(summary_filepath),
        'pivot_file': str(pivot_filepath)
    }

def show_top_products(sku_stats, top_n=10):
    """Mostrar los productos con mayores proyecciones."""
    
    print(f"\n🏆 Top {top_n} Productos por Forecast Total (12 meses)")
    print("=" * 60)
    
    top_products = sku_stats.nlargest(top_n, 'total_forecast_12_months')
    
    print(" Rank | SKU      | Total 12M | Prom/Mes | Min  | Max  | Desv.Std")
    print("-" * 65)
    
    for i, (_, row) in enumerate(top_products.iterrows(), 1):
        print(f" {i:4} | {row['sku']:8} | {row['total_forecast_12_months']:9,.0f} | {row['avg_monthly_forecast']:8.1f} | {row['min_monthly_forecast']:4.0f} | {row['max_monthly_forecast']:4.0f} | {row['std_dev']:8.1f}")

def show_forecast_overview(df):
    """Mostrar resumen general de todos los forecasts."""
    
    print(f"\n📈 Resumen General de Forecasts")
    print("=" * 40)
    
    # Estadísticas generales
    total_products = df['sku'].nunique()
    total_forecast = df['forecasted_quantity'].sum()
    avg_monthly = df['forecasted_quantity'].mean()
    
    print(f"📦 Total productos con forecast: {total_products:,}")
    print(f"📊 Total proyectado (12 meses): {total_forecast:,} unidades")
    print(f"📈 Promedio mensual general: {avg_monthly:.1f} unidades")
    
    # Por mes
    monthly_totals = df.groupby('month_name')['forecasted_quantity'].sum()
    max_month = monthly_totals.idxmax()
    min_month = monthly_totals.idxmin()
    
    print(f"\n📅 Estacionalidad General:")
    print(f"   🔥 Mes con mayor demanda: {max_month} ({monthly_totals[max_month]:,} unidades)")
    print(f"   ❄️  Mes con menor demanda: {min_month} ({monthly_totals[min_month]:,} unidades)")
    
    # Por trimestre
    quarterly_totals = df.groupby('quarter')['forecasted_quantity'].sum()
    print(f"\n📊 Por Trimestre:")
    for quarter, total in quarterly_totals.items():
        print(f"   {quarter}: {total:,} unidades")

def show_quality_analysis(df, summary_df):
    """Mostrar análisis de calidad de los forecasts sin modificar datos."""
    
    print("\n📊 Análisis de Calidad de Forecasts")
    print("=" * 50)
    
    # Estadísticas descriptivas generales (solo informativo)
    quantities = df['forecasted_quantity']
    
    print(f"📈 Distribución Global de Forecasts:")
    print(f"   Total registros: {len(df):,}")
    print(f"   Mínimo: {quantities.min()}")
    print(f"   Q25: {quantities.quantile(0.25):,.0f}")
    print(f"   Mediana: {quantities.median():,.0f}")
    print(f"   Q75: {quantities.quantile(0.75):,.0f}")
    print(f"   Q90: {quantities.quantile(0.90):,.0f}")
    print(f"   Q99: {quantities.quantile(0.99):,.0f}")
    print(f"   Máximo: {quantities.max():,}")
    print(f"   Media: {quantities.mean():.1f}")
    print(f"   Desv. Estándar: {quantities.std():.1f}")
    
    # Análisis por categorías de rotación
    print(f"\n🏷️ Análisis por Categorías de Rotación:")
    
    # Categorizar SKUs por volumen total proyectado
    high_volume = summary_df[summary_df['total_forecast_12_months'] >= 1000]
    medium_volume = summary_df[(summary_df['total_forecast_12_months'] >= 100) & 
                              (summary_df['total_forecast_12_months'] < 1000)]
    low_volume = summary_df[summary_df['total_forecast_12_months'] < 100]
    
    print(f"   🔥 Alta rotación (≥1000/año): {len(high_volume)} SKUs")
    if len(high_volume) > 0:
        print(f"      Promedio mensual: {high_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {high_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {high_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    print(f"   📊 Media rotación (100-999/año): {len(medium_volume)} SKUs")
    if len(medium_volume) > 0:
        print(f"      Promedio mensual: {medium_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {medium_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {medium_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    print(f"   📉 Baja rotación (<100/año): {len(low_volume)} SKUs")
    if len(low_volume) > 0:
        print(f"      Promedio mensual: {low_volume['avg_monthly_forecast'].mean():.1f}")
        print(f"      Rango típico: {low_volume['avg_monthly_forecast'].quantile(0.25):.0f} - {low_volume['avg_monthly_forecast'].quantile(0.75):.0f}")
    
    # Verificar consistencia
    print(f"\n✅ Verificación de Consistencia:")
    inconsistent = summary_df[summary_df['max_monthly_forecast'] < summary_df['avg_monthly_forecast']]
    print(f"   📊 SKUs con max < promedio: {len(inconsistent)}")
    
    negative_skus = summary_df[summary_df['min_monthly_forecast'] < 0]
    print(f"   🔴 SKUs con valores negativos: {len(negative_skus)}")
    
    if len(inconsistent) == 0 and len(negative_skus) == 0:
        print(f"   ✅ Todos los forecasts son consistentes y válidos")
    
    print(f"\n💡 Interpretación:")
    print(f"   🎯 Los forecasts se generaron con validación individual por SKU")
    print(f"   📊 Cada producto tiene límites basados en su historial específico")
    print(f"   ✅ No se aplicó limpieza global que podría distorsionar patrones naturales")



def parse_arguments():
    """Parsear argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description='Generador de Forecasts para Todos los Productos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos disponibles:
  db      - Guardar forecasts en base de datos (default)
  report  - Generar archivos CSV de reporte

Ejemplos:
  python generate_all_forecasts.py --mode db
  python generate_all_forecasts.py --mode report
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['db', 'report'],
        default='db',
        help='Modo de operación: "db" para base de datos, "report" para archivos CSV (default: db)'
    )
    
    return parser.parse_args()


def save_to_database(df_with_stats: pd.DataFrame) -> Dict[str, int]:
    """Guardar forecasts en base de datos."""
    print("\n" + "="*70)
    print("💾 GUARDANDO EN BASE DE DATOS")
    print("="*70)
    
    try:
        db_updater = DatabaseForecastUpdater()
        result = db_updater.upsert_forecasts(df_with_stats)
        
        print(f"✅ Forecasts guardados en base de datos exitosamente")
        print(f"   📊 Registros procesados: {result['total_processed']:,}")
        print(f"   🗄️  Total registros en DB: {result['total_records_in_db']:,}")
        print(f"   📦 SKUs únicos en DB: {result['unique_skus_in_db']:,}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error guardando en base de datos: {str(e)}")
        raise


def main():
    """Función principal con soporte para múltiples modos."""
    
    # Parsear argumentos
    args = parse_arguments()
    
    print("🎯 Generador de Forecasts - Todos los Productos")
    print("=" * 70)
    print(f"📋 Modo seleccionado: {args.mode.upper()}")
    
    if args.mode == 'report':
        print(f"📁 Los archivos CSV se guardarán en: {FORECASTS_DIR}")
    else:
        print(f"🗄️  Los forecasts se guardarán en la base de datos")
    
    print("=" * 70)
    
    try:
        # 1. Generar forecasts para todos los productos
        all_forecasts = generate_all_forecasts()
        
        if not all_forecasts:
            print("❌ No se pudieron generar forecasts")
            return 1
        
        # 2. Convertir a DataFrame
        df = convert_to_dataframe(all_forecasts)
        
        if df.empty:
            print("❌ DataFrame vacío")
            return 1
        
        # 3. Agregar estadísticas
        df_with_stats, sku_stats = add_summary_statistics(df)
        
        # 4. Proceso según el modo seleccionado
        if args.mode == 'db':
            # Modo Base de Datos
            save_result = save_to_database(df_with_stats)
            
            # Mostrar resúmenes
            show_forecast_overview(df)
            show_top_products(sku_stats)
            
            # 5. RESUMEN FINAL - Modo DB
            print(f"\n" + "="*70)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE!")
            print("="*70)
            
            print(f"\n🗄️  Forecasts guardados en base de datos:")
            print(f"   📊 Registros procesados: {save_result['total_processed']:,}")
            print(f"   🗄️  Total registros en DB: {save_result['total_records_in_db']:,}")
            print(f"   📦 SKUs únicos en DB: {save_result['unique_skus_in_db']:,}")
            
            print(f"\n💡 Uso de los datos:")
            print(f"   🎯 Forecasts disponibles para consulta en la tabla 'forecast'")
            print(f"   📊 Listos para análisis de negocio y toma de decisiones")
            print(f"   ✅ Actualizados automáticamente con timestamp")
            
        else:
            # Modo Reporte (CSV)
            print("\n" + "="*70)
            print("📊 EXPORTANDO FORECASTS")
            print("="*70)
            
            files_created = export_to_csv(df_with_stats, sku_stats)
            
            # Mostrar resúmenes
            show_forecast_overview(df)
            show_top_products(sku_stats)
            
            # Análisis de calidad (solo informativo)
            print("\n" + "="*70)
            print("📊 ANÁLISIS DE CALIDAD DE FORECASTS")
            print("="*70)
            
            # Solo mostrar estadísticas descriptivas, sin limpiar
            show_quality_analysis(df_with_stats, sku_stats)
            
            # RESUMEN FINAL - Modo Report
            print(f"\n" + "="*70)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE!")
            print("="*70)
            
            print(f"\n📁 Archivos de Forecasts:")
            for file_type, filename in files_created.items():
                print(f"   • {filename}")
            
            print(f"\n📍 Ubicación de archivos: {FORECASTS_DIR}")
            print(f"\n💡 Uso de los archivos:")
            print(f"   📊 Forecasts validados individualmente por SKU")
            print(f"   🎯 Listos para análisis de negocio y toma de decisiones")
            print(f"   ✅ Sin distorsión por limpieza global artificial")
            print(f"   📈 Cada producto respeta sus patrones históricos específicos")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
