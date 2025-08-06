"""
ProductionForecastReader para Sales Engine

Cliente para leer datos de la tabla production_forecast en base de datos.
Actualizado para nueva estructura sin current_sales.
"""

import os
import pandas as pd
import psycopg2
import psycopg2.pool
from datetime import date, datetime
from typing import Dict, List, Optional, Any
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
        """
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"El año debe ser un entero válido, recibido: {year}")
        
        logger.info(f"Obteniendo production_forecasts para {month}/{year}")
        
        query = """
        SELECT 
            id, sku, product_name, year, month, month_name,
            forecast_quantity, inventory_available, production_needed,
            priority, is_valid_product, created_at, updated_at
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
        """
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
    
    def get_production_forecast_for_sku(self, sku: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtener production_forecast para un SKU específico.
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
                df = pd.read_sql_query(base_query, conn, params=params)
                
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
    
    def get_production_forecast_summary_all(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtener resumen general de todos los production_forecasts.
        """
        if year is None:
            logger.info("Obteniendo resumen general de production_forecasts (todos los años)")
            query = """
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
            """
            params = ()
        else:
            logger.info(f"Obteniendo resumen general de production_forecasts para el año {year}")
            query = """
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
            WHERE year = %s
            """
            params = (year,)
        
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
                        'year': year if year else "todos"
                    }
                    
                    logger.success("Resumen de production_forecasts obtenido exitosamente", **summary)
                    
                    return summary
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo resumen: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo resumen: {e}")
            raise


def get_production_forecasts_by_month(month: int, year: int) -> pd.DataFrame:
    """Función de conveniencia para obtener production_forecasts por mes."""
    reader = ProductionForecastReader()
    return reader.get_production_forecasts_by_month(month, year)


if __name__ == "__main__":
    import sys
    
    try:
        reader = ProductionForecastReader()
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Resumen general
        print(f"\n🏭 Resumen de Production Forecasts ({current_year}):")
        print("=" * 60)
        summary = reader.get_production_forecast_summary_all(current_year)
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")
        
        # Meses disponibles
        months = reader.get_available_months(current_year)
        print(f"\n📅 Meses Disponibles ({current_year}): {months}")
        
        # Datos del mes actual si disponible
        if current_month in months:
            current_data = reader.get_production_forecasts_by_month(current_month, current_year)
            if not current_data.empty:
                print(f"\n📈 Production Forecasts - {current_month}/{current_year}:")
                print(f"   Registros: {len(current_data)}")
                print(f"   SKUs únicos: {current_data['sku'].nunique()}")
                print(f"   Producción total requerida: {current_data['production_needed'].sum():.2f}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)