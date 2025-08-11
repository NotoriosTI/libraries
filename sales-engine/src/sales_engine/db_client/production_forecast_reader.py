"""
ProductionForecastReader para Sales Engine

Cliente para leer datos de la tabla production_forecast con filtrado por prioridad.
Actualizado para nueva estructura sin current_sales.
"""

import os
import pandas as pd
import psycopg2
import psycopg2.pool
from datetime import date, datetime
from typing import Dict, List, Optional, Any, Literal
from contextlib import contextmanager

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("sales-engine-production-forecast-reader")
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
    """Cliente para leer datos desde la tabla production_forecast con filtrado por prioridad."""
    
    # Priority hierarchy mapping
    PRIORITY_LEVELS = {
        'ALTA': 3,
        'MEDIA': 2,
        'BAJA': 1
    }
    
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
    
    def _get_priority_filter(self, minimum_priority: str) -> tuple:
        """Generate priority filter SQL and valid priorities list."""
        if minimum_priority.upper() not in self.PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority: {minimum_priority}. Must be one of: {list(self.PRIORITY_LEVELS.keys())}")
        
        min_level = self.PRIORITY_LEVELS[minimum_priority.upper()]
        valid_priorities = [p for p, level in self.PRIORITY_LEVELS.items() if level >= min_level]
        
        priority_placeholders = ','.join(['%s'] * len(valid_priorities))
        priority_filter = f"AND priority IN ({priority_placeholders})"
        
        return priority_filter, valid_priorities
    
    def get_production_forecasts_by_month(self, month: int, year: int, minimum_priority: Literal['baja', 'media', 'alta'] = 'baja') -> pd.DataFrame:
        """
        Obtener production_forecast data filtrado por prioridad mínima.
        
        Args:
            month: Mes (1-12)
            year: Año
            minimum_priority: Prioridad mínima ('alta', 'media', 'baja'). Default: 'baja' (todos)
        """
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"El año debe ser un entero válido, recibido: {year}")
        
        # Convert to uppercase for robustness
        minimum_priority = minimum_priority.upper()
        priority_filter, valid_priorities = self._get_priority_filter(minimum_priority)
        
        logger.info(f"Obteniendo production_forecasts para {month}/{year} con prioridad >= {minimum_priority}")
        
        query = f"""
        SELECT 
            id, sku, product_name, year, month, month_name,
            forecast_quantity, inventory_available, production_needed,
            priority, is_valid_product, created_at, updated_at
        FROM production_forecast 
        WHERE month = %s AND year = %s {priority_filter}
        ORDER BY 
            CASE priority 
                WHEN 'ALTA' THEN 1 
                WHEN 'MEDIA' THEN 2 
                WHEN 'BAJA' THEN 3 
            END,
            production_needed DESC, sku
        """
        
        params = [month, year] + valid_priorities
        
        try:
            with self.get_connection() as conn:
                # Convertir la conexión psycopg2 a SQLAlchemy para evitar warnings
                from sqlalchemy import create_engine
                engine = create_engine('postgresql://', creator=lambda: conn)
                df = pd.read_sql_query(query, engine, params=params)
                
                logger.success(f"Production forecasts obtenidos exitosamente", 
                             month=month, 
                             year=year,
                             minimum_priority=minimum_priority,
                             total_records=len(df),
                             unique_skus=df['sku'].nunique() if not df.empty else 0)
                
                return df
                
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo production_forecasts para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo production_forecasts para {month}/{year}: {e}")
            raise
    
    def get_production_forecast_summary(self, month: int, year: int, minimum_priority: Literal['baja', 'media', 'alta'] = 'baja') -> Dict[str, Any]:
        """
        Obtener resumen filtrado por prioridad mínima.
        """
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"El año debe ser un entero válido, recibido: {year}")
        
        # Convert to uppercase for robustness
        minimum_priority = minimum_priority.upper()
        priority_filter, valid_priorities = self._get_priority_filter(minimum_priority)
        
        logger.info(f"Obteniendo resumen de production_forecasts para {month}/{year} con prioridad >= {minimum_priority}")
        
        query = f"""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT sku) as unique_skus,
            SUM(forecast_quantity) as total_forecast_quantity,
            SUM(inventory_available) as total_inventory_available,
            SUM(production_needed) as total_production_needed,
            AVG(forecast_quantity) as avg_forecast_quantity,
            AVG(inventory_available) as avg_inventory_available,
            AVG(production_needed) as avg_production_needed,
            COUNT(CASE WHEN priority = 'ALTA' THEN 1 END) as alta_priority_count,
            COUNT(CASE WHEN priority = 'MEDIA' THEN 1 END) as media_priority_count,
            COUNT(CASE WHEN priority = 'BAJA' THEN 1 END) as baja_priority_count,
            COUNT(CASE WHEN is_valid_product = true THEN 1 END) as valid_products_count,
            COUNT(CASE WHEN is_valid_product = false THEN 1 END) as invalid_products_count
        FROM production_forecast 
        WHERE month = %s AND year = %s {priority_filter}
        """
        
        params = [month, year] + valid_priorities
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    
                    summary = {
                        'total_records': result[0],
                        'unique_skus': result[1],
                        'total_forecast_quantity': float(result[2]) if result[2] else 0,
                        'total_inventory_available': float(result[3]) if result[3] else 0,
                        'total_production_needed': float(result[4]) if result[4] else 0,
                        'avg_forecast_quantity': float(result[5]) if result[5] else 0,
                        'avg_inventory_available': float(result[6]) if result[6] else 0,
                        'avg_production_needed': float(result[7]) if result[7] else 0,
                        'alta_priority_count': result[8],
                        'media_priority_count': result[9],
                        'baja_priority_count': result[10],
                        'valid_products_count': result[11],
                        'invalid_products_count': result[12],
                        'month': month,
                        'year': year,
                        'minimum_priority': minimum_priority
                    }
                    
                    logger.success("Resumen de production_forecasts obtenido exitosamente", **summary)
                    
                    return summary
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo resumen para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo resumen para {month}/{year}: {e}")
            raise
    
    def get_production_forecast_for_sku(self, sku: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtener production_forecast para un SKU específico.
        Note: No priority filter since this is for a specific SKU.
        """
        if year is None:
            year = datetime.now().year
            
        logger.info(f"Obteniendo production_forecast para SKU {sku}", month=month, year=year)
        
        base_query = """
        SELECT 
            id, sku, product_name, year, month, month_name,
            forecast_quantity, inventory_available, production_needed,
            priority, is_valid_product, created_at, updated_at
        FROM production_forecast 
        WHERE sku = %s AND year = %s
        """
        
        params = [sku, year]
        
        if month is not None:
            if not isinstance(month, int) or month < 1 or month > 12:
                raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
            base_query += " AND month = %s"
            params.append(month)
        
        base_query += " ORDER BY month, created_at"
        
        try:
            with self.get_connection() as conn:
                # Convertir la conexión psycopg2 a SQLAlchemy para evitar warnings
                from sqlalchemy import create_engine
                engine = create_engine('postgresql://', creator=lambda: conn)
                df = pd.read_sql_query(base_query, engine, params=params)
                
                if df.empty:
                    logger.warning(f"No se encontraron production_forecasts para SKU {sku}", month=month)
                    return {}
                
                result = {
                    'sku': sku,
                    'total_records': len(df),
                    'total_forecast_quantity': df['forecast_quantity'].sum(),
                    'total_inventory_available': df['inventory_available'].sum(),
                    'total_production_needed': df['production_needed'].sum(),
                    'avg_forecast_quantity': df['forecast_quantity'].mean(),
                    'avg_inventory_available': df['inventory_available'].mean(),
                    'avg_production_needed': df['production_needed'].mean(),
                    'priority_distribution': df['priority'].value_counts().to_dict(),
                    'is_valid_product': df['is_valid_product'].iloc[0] if len(df) > 0 else None,
                    'records_by_month': df.set_index('month')[['forecast_quantity', 'inventory_available', 'production_needed']].to_dict('index'),
                    'summary': df.iloc[0].to_dict() if len(df) > 0 else {}
                }
                
                logger.success(f"Production forecast obtenido para SKU {sku}", 
                             total_records=result['total_records'],
                             total_production_needed=result['total_production_needed'])
                
                return result
                
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo production_forecast para SKU {sku}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo production_forecast para SKU {sku}: {e}")
            raise
    
    def get_available_months(self, year: Optional[int] = None) -> List[int]:
        """
        Obtener lista de meses disponibles en la tabla production_forecast.
        """
        if year is None:
            logger.info("Obteniendo meses disponibles en production_forecast (todos los años)")
            query = "SELECT DISTINCT month FROM production_forecast ORDER BY month"
            params = ()
        else:
            logger.info(f"Obteniendo meses disponibles en production_forecast para el año {year}")
            query = "SELECT DISTINCT month FROM production_forecast WHERE year = %s ORDER BY month"
            params = (year,)
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    
                    months = [row[0] for row in results]
                    
                    logger.success(f"Meses disponibles obtenidos", 
                                 available_months=months,
                                 year=year if year else "todos")
                    
                    return months
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo meses disponibles: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo meses disponibles: {e}")
            raise
    
    def get_production_forecast_summary_all(self, year: Optional[int] = None, minimum_priority: Literal['baja', 'media', 'alta'] = 'baja') -> Dict[str, Any]:
        """
        Obtener resumen general filtrado por prioridad mínima.
        """
        # Convert to uppercase for robustness
        minimum_priority = minimum_priority.upper()
        priority_filter, valid_priorities = self._get_priority_filter(minimum_priority)
        
        if year is None:
            logger.info(f"Obteniendo resumen general de production_forecasts (todos los años) con prioridad >= {minimum_priority}")
            query = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sku) as unique_skus,
                COUNT(DISTINCT month) as available_months,
                MIN(created_at) as earliest_date,
                MAX(created_at) as latest_date,
                SUM(forecast_quantity) as total_forecast_quantity,
                SUM(inventory_available) as total_inventory_available,
                SUM(production_needed) as total_production_needed,
                AVG(forecast_quantity) as avg_forecast_quantity,
                AVG(inventory_available) as avg_inventory_available,
                AVG(production_needed) as avg_production_needed,
                COUNT(CASE WHEN priority = 'ALTA' THEN 1 END) as alta_priority_count,
                COUNT(CASE WHEN priority = 'MEDIA' THEN 1 END) as media_priority_count,
                COUNT(CASE WHEN priority = 'BAJA' THEN 1 END) as baja_priority_count,
                COUNT(CASE WHEN is_valid_product = true THEN 1 END) as valid_products_count,
                COUNT(CASE WHEN is_valid_product = false THEN 1 END) as invalid_products_count
            FROM production_forecast
            WHERE 1=1 {priority_filter}
            """
            params = valid_priorities
        else:
            logger.info(f"Obteniendo resumen general de production_forecasts para el año {year} con prioridad >= {minimum_priority}")
            query = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sku) as unique_skus,
                COUNT(DISTINCT month) as available_months,
                MIN(created_at) as earliest_date,
                MAX(created_at) as latest_date,
                SUM(forecast_quantity) as total_forecast_quantity,
                SUM(inventory_available) as total_inventory_available,
                SUM(production_needed) as total_production_needed,
                AVG(forecast_quantity) as avg_forecast_quantity,
                AVG(inventory_available) as avg_inventory_available,
                AVG(production_needed) as avg_production_needed,
                COUNT(CASE WHEN priority = 'ALTA' THEN 1 END) as alta_priority_count,
                COUNT(CASE WHEN priority = 'MEDIA' THEN 1 END) as media_priority_count,
                COUNT(CASE WHEN priority = 'BAJA' THEN 1 END) as baja_priority_count,
                COUNT(CASE WHEN is_valid_product = true THEN 1 END) as valid_products_count,
                COUNT(CASE WHEN is_valid_product = false THEN 1 END) as invalid_products_count
            FROM production_forecast
            WHERE year = %s {priority_filter}
            """
            params = [year] + valid_priorities
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    
                    summary = {
                        'total_records': result[0],
                        'unique_skus': result[1],
                        'available_months': result[2],
                        'earliest_date': result[3],
                        'latest_date': result[4],
                        'total_forecast_quantity': float(result[5]) if result[5] else 0,
                        'total_inventory_available': float(result[6]) if result[6] else 0,
                        'total_production_needed': float(result[7]) if result[7] else 0,
                        'avg_forecast_quantity': float(result[8]) if result[8] else 0,
                        'avg_inventory_available': float(result[9]) if result[9] else 0,
                        'avg_production_needed': float(result[10]) if result[10] else 0,
                        'alta_priority_count': result[11],
                        'media_priority_count': result[12],
                        'baja_priority_count': result[13],
                        'valid_products_count': result[14],
                        'invalid_products_count': result[15],
                        'year': year if year else "todos",
                        'minimum_priority': minimum_priority
                    }
                    
                    logger.success("Resumen de production_forecasts obtenido exitosamente", **summary)
                    
                    return summary
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo resumen: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo resumen: {e}")
            raise


def get_production_forecasts_by_month(month: int, year: int, minimum_priority: Literal['baja', 'media', 'alta'] = 'baja') -> pd.DataFrame:
    """Función de conveniencia para obtener production_forecasts filtrados por prioridad."""
    reader = ProductionForecastReader()
    return reader.get_production_forecasts_by_month(month, year, minimum_priority)


if __name__ == "__main__":
    import sys
    
    try:
        reader = ProductionForecastReader()
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Resumen solo productos ALTA prioridad
        print(f"\n🚨 Resumen de Production Forecasts - prioridad >= MEDIA ({current_year}):")
        print("=" * 60)
        summary_media = reader.get_production_forecast_summary_all(current_year, minimum_priority='media')
        for key, value in summary_media.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")
        
        # Meses disponibles
        months = reader.get_available_months(current_year)
        print(f"\n📅 Meses Disponibles ({current_year}): {months}")
        
        # Solo productos de MEDIA prioridad para el mes actual
        if current_month in months:
            alta_data = reader.get_production_forecasts_by_month(current_month, current_year, minimum_priority='media')
            if not alta_data.empty:
                print(f"\n🚨 Production Forecasts MEDIA prioridad - {current_month}/{current_year}:")
                print(f"   Registros: {len(alta_data)}")
                print(f"   SKUs únicos: {alta_data['sku'].nunique()}")
                print(f"   Producción total requerida: {alta_data['production_needed'].sum():.2f}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)