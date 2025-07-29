"""
Test para leer datos de la tabla production_forecast

Este script lee todos los datos de la tabla production_forecast para un año y mes específico
y devuelve un DataFrame con la información completa.
"""

import os
import sys
import pandas as pd
import psycopg2
import psycopg2.pool
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

# Agregar el directorio src al path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("production-forecast-reader")
except ImportError:
    class LoggerFallback:
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️  {msg}")
    logger = LoggerFallback()

try:
    from config_manager import secrets
except ImportError:
    print("⚠️  config_manager no disponible, usando configuración básica")
    secrets = None


class ProductionForecastReader:
    """Cliente para leer datos desde la tabla production_forecast."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.logger = logger
        self._connection_pool = None
        
        logger.info("ProductionForecastReader inicializado", 
                   environment=os.getenv('ENVIRONMENT', 'local'),
                   use_test_odoo=use_test_odoo,
                   component="production_forecast_reader")
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Obtener parámetros de conexión."""
        if secrets:
            try:
                db_config = secrets.get_database_config()
                db_config['port'] = int(db_config['port'])
                return db_config
            except Exception as e:
                logger.error(f"Error obteniendo configuración de secrets: {e}")
        
        # Configuración por defecto desde variables de entorno
        return {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'salesdb'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }
    
    @contextmanager
    def get_connection(self):
        """Context manager para obtener conexión a la base de datos."""
        if not self._connection_pool:
            params = self._get_connection_params()
            self._connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1, maxconn=5, **params
            )
            logger.info("Pool de conexiones de base de datos creado",
                       host=params['host'], database=params['database'],
                       component="production_forecast_reader")
        
        conn = self._connection_pool.getconn()
        try:
            yield conn
        finally:
            self._connection_pool.putconn(conn)
    
    def get_production_forecasts_by_month(self, month: int, year: int) -> pd.DataFrame:
        """
        Obtener todos los datos de production_forecast para un mes y año específico.
        
        Args:
            month (int): Número del mes (1-12)
            year (int): Año específico
            
        Returns:
            pd.DataFrame: DataFrame con todos los datos de production_forecast para el mes/año
            
        Raises:
            ValueError: Si el mes no está en el rango válido (1-12)
            Exception: Si hay error en la consulta a la base de datos
        """
        # Validar entrada
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"El año debe ser un entero válido, recibido: {year}")
        
        logger.info(f"Obteniendo production_forecasts para {month}/{year}")
        
        query = """
        SELECT 
            id,
            sku,
            product_name,
            year,
            month,
            month_name,
            forecast_quantity,
            current_sales,
            inventory_available,
            production_needed,
            priority,
            is_valid_product,
            created_at,
            updated_at
        FROM production_forecast 
        WHERE month = %s AND year = %s
        ORDER BY production_needed DESC, sku
        """
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(month, year))
                
                logger.success(f"Production forecasts obtenidos exitosamente", 
                             month=month, 
                             year=year,
                             total_records=len(df),
                             unique_skus=df['sku'].nunique() if not df.empty else 0)
                
                return df
                
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo production_forecasts para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo production_forecasts para {month}/{year}: {e}")
            raise
    
    def get_production_forecast_summary(self, month: int, year: int) -> Dict[str, Any]:
        """
        Obtener resumen de production_forecast para un mes y año específico.
        
        Args:
            month (int): Número del mes (1-12)
            year (int): Año específico
            
        Returns:
            Dict[str, Any]: Resumen de estadísticas de production_forecast
        """
        # Validar entrada
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"El año debe ser un entero válido, recibido: {year}")
        
        logger.info(f"Obteniendo resumen de production_forecasts para {month}/{year}")
        
        query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT sku) as unique_skus,
            SUM(forecast_quantity) as total_forecast_quantity,
            SUM(current_sales) as total_current_sales,
            SUM(inventory_available) as total_inventory_available,
            SUM(production_needed) as total_production_needed,
            AVG(forecast_quantity) as avg_forecast_quantity,
            AVG(current_sales) as avg_current_sales,
            AVG(inventory_available) as avg_inventory_available,
            AVG(production_needed) as avg_production_needed,
            COUNT(CASE WHEN priority = 'ALTA' THEN 1 END) as alta_priority_count,
            COUNT(CASE WHEN priority = 'MEDIA' THEN 1 END) as media_priority_count,
            COUNT(CASE WHEN priority = 'BAJA' THEN 1 END) as baja_priority_count,
            COUNT(CASE WHEN is_valid_product = true THEN 1 END) as valid_products_count,
            COUNT(CASE WHEN is_valid_product = false THEN 1 END) as invalid_products_count
        FROM production_forecast 
        WHERE month = %s AND year = %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (month, year))
                    result = cursor.fetchone()
                    
                    summary = {
                        'total_records': result[0],
                        'unique_skus': result[1],
                        'total_forecast_quantity': float(result[2]) if result[2] else 0,
                        'total_current_sales': float(result[3]) if result[3] else 0,
                        'total_inventory_available': float(result[4]) if result[4] else 0,
                        'total_production_needed': float(result[5]) if result[5] else 0,
                        'avg_forecast_quantity': float(result[6]) if result[6] else 0,
                        'avg_current_sales': float(result[7]) if result[7] else 0,
                        'avg_inventory_available': float(result[8]) if result[8] else 0,
                        'avg_production_needed': float(result[9]) if result[9] else 0,
                        'alta_priority_count': result[10],
                        'media_priority_count': result[11],
                        'baja_priority_count': result[12],
                        'valid_products_count': result[13],
                        'invalid_products_count': result[14],
                        'month': month,
                        'year': year
                    }
                    
                    logger.success("Resumen de production_forecasts obtenido exitosamente", **summary)
                    
                    return summary
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo resumen para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo resumen para {month}/{year}: {e}")
            raise


def get_production_forecasts_by_month(month: int, year: int) -> pd.DataFrame:
    """
    Función de conveniencia para obtener production_forecasts por mes.
    
    Args:
        month (int): Número del mes (1-12)
        year (int): Año específico
        
    Returns:
        pd.DataFrame: DataFrame con todos los datos de production_forecast
    """
    reader = ProductionForecastReader()
    return reader.get_production_forecasts_by_month(month, year)


# Script de ejemplo/testing
if __name__ == "__main__":
    import sys
    
    # Ejemplo de uso
    try:
        reader = ProductionForecastReader()
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        print(f"\n🏭 Production Forecast Reader - Test")
        print("=" * 60)
        
        # Mostrar resumen del mes actual
        print(f"\n📊 Resumen de Production Forecasts ({current_month}/{current_year}):")
        print("=" * 60)
        summary = reader.get_production_forecast_summary(current_month, current_year)
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")
        
        # Obtener datos completos del mes actual
        print(f"\n📋 Datos completos de Production Forecasts ({current_month}/{current_year}):")
        print("=" * 60)
        df = reader.get_production_forecasts_by_month(current_month, current_year)
        
        if not df.empty:
            print(f"   Total registros: {len(df)}")
            print(f"   SKUs únicos: {df['sku'].nunique()}")
            print(f"   Total producción necesaria: {df['production_needed'].sum():.2f}")
            print(f"   Promedio producción necesaria: {df['production_needed'].mean():.2f}")
            
            # Mostrar top 10 por producción necesaria
            print(f"\n   Top 10 por producción necesaria:")
            top_10 = df.nlargest(10, 'production_needed')[['sku', 'product_name', 'production_needed', 'priority']]
            for _, row in top_10.iterrows():
                print(f"     {row['sku']}: {row['production_needed']:.2f} ({row['priority']}) - {row['product_name']}")
            
            # Mostrar distribución por prioridad
            print(f"\n   Distribución por prioridad:")
            priority_counts = df['priority'].value_counts()
            for priority, count in priority_counts.items():
                print(f"     {priority}: {count} productos")
            
            # Mostrar productos válidos vs inválidos
            valid_count = df['is_valid_product'].sum()
            invalid_count = len(df) - valid_count
            print(f"\n   Productos válidos: {valid_count}")
            print(f"   Productos inválidos: {invalid_count}")
            
        else:
            print("   No se encontraron datos para el mes/año especificado")
        
        # Ejemplo con mes anterior
        previous_month = current_month - 1 if current_month > 1 else 12
        previous_year = current_year if current_month > 1 else current_year - 1
        
        print(f"\n📋 Datos del mes anterior ({previous_month}/{previous_year}):")
        print("=" * 60)
        df_previous = reader.get_production_forecasts_by_month(previous_month, previous_year)
        
        if not df_previous.empty:
            print(f"   Total registros: {len(df_previous)}")
            print(f"   SKUs únicos: {df_previous['sku'].nunique()}")
            print(f"   Total producción necesaria: {df_previous['production_needed'].sum():.2f}")
        else:
            print("   No se encontraron datos para el mes anterior")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1) 