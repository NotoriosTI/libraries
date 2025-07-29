"""
ForecastReader para Sales Engine

Cliente para leer forecasts de la tabla forecast en base de datos.
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
    logger = PrettyLogger("sales-engine-forecast-reader")
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


class ForecastReader:
    """Cliente para leer forecasts desde la tabla forecast."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.logger = logger
        self._connection_pool = None
        
        logger.info("ForecastReader inicializado", 
                   environment=os.getenv('ENVIRONMENT', 'local'),
                   use_test_odoo=use_test_odoo,
                   component="forecast_reader")
    
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
                       component="forecast_reader")
        
        conn = self._connection_pool.getconn()
        try:
            yield conn
        finally:
            self._connection_pool.putconn(conn)
    
    def get_forecasts_by_month(self, month: int, year: Optional[int] = None) -> Dict[str, float]:
        """
        Obtener todas las predicciones para un mes específico.
        
        Args:
            month (int): Número del mes (1-12)
            year (Optional[int]): Año específico. Si es None, usa el año actual.
            
        Returns:
            Dict[str, float]: Diccionario con SKU como clave y cantidad predicha como valor
            
        Raises:
            ValueError: Si el mes no está en el rango válido (1-12)
            Exception: Si hay error en la consulta a la base de datos
        """
        # Validar entrada
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        # Usar año actual si no se especifica
        if year is None:
            year = datetime.now().year
        
        logger.info(f"Obteniendo forecasts para {month}/{year}")
        
        query = """
        SELECT 
            sku,
            SUM(forecasted_quantity) as total_forecasted_quantity
        FROM forecast 
        WHERE month = %s AND year = %s
        GROUP BY sku
        ORDER BY sku
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (month, year))
                    results = cursor.fetchall()
                    
                    # Convertir resultados a diccionario
                    forecast_dict = {
                        row[0]: float(row[1]) for row in results
                    }
                    
                    logger.success(f"Forecasts obtenidos exitosamente", 
                                 month=month, 
                                 year=year,
                                 total_skus=len(forecast_dict),
                                 total_quantity=sum(forecast_dict.values()))
                    
                    return forecast_dict
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo forecasts para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo forecasts para {month}/{year}: {e}")
            raise
    
    def get_forecasts_by_month_detailed(self, month: int, year: Optional[int] = None) -> pd.DataFrame:
        """
        Obtener todas las predicciones para un mes específico con información detallada.
        
        Args:
            month (int): Número del mes (1-12)
            year (Optional[int]): Año específico. Si es None, usa el año actual.
            
        Returns:
            pd.DataFrame: DataFrame con información detallada de forecasts
        """
        # Validar entrada
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
        
        # Usar año actual si no se especifica
        if year is None:
            year = datetime.now().year
        
        logger.info(f"Obteniendo forecasts detallados para {month}/{year}")
        
        query = """
        SELECT 
            sku,
            forecast_date,
            forecasted_quantity,
            year,
            month,
            month_name,
            quarter,
            total_forecast_12_months,
            avg_monthly_forecast,
            created_at,
            updated_at
        FROM forecast 
        WHERE month = %s AND year = %s
        ORDER BY sku, forecast_date
        """
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(month, year))
                
                logger.success(f"Forecasts detallados obtenidos exitosamente", 
                             month=month, 
                             year=year,
                             total_records=len(df),
                             unique_skus=df['sku'].nunique() if not df.empty else 0)
                
                return df
                
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo forecasts detallados para {month}/{year}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo forecasts detallados para {month}/{year}: {e}")
            raise
    
    def get_forecast_for_sku(self, sku: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtener forecast para un SKU específico.
        
        Args:
            sku (str): SKU del producto
            month (Optional[int]): Mes específico (1-12). Si es None, obtiene todos los meses.
            year (Optional[int]): Año específico. Si es None, usa el año actual.
            
        Returns:
            Dict[str, Any]: Información de forecast del SKU
        """
        # Usar año actual si no se especifica
        if year is None:
            year = datetime.now().year
            
        logger.info(f"Obteniendo forecast para SKU {sku}", month=month, year=year)
        
        base_query = """
        SELECT 
            sku,
            forecast_date,
            forecasted_quantity,
            year,
            month,
            month_name,
            quarter,
            total_forecast_12_months,
            avg_monthly_forecast,
            created_at,
            updated_at
        FROM forecast 
        WHERE sku = %s AND year = %s
        """
        
        params = [sku, year]
        
        if month is not None:
            if not isinstance(month, int) or month < 1 or month > 12:
                raise ValueError(f"El mes debe ser un entero entre 1 y 12, recibido: {month}")
            base_query += " AND month = %s"
            params.append(month)
        
        base_query += " ORDER BY forecast_date"
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(base_query, conn, params=params)
                
                if df.empty:
                    logger.warning(f"No se encontraron forecasts para SKU {sku}", month=month)
                    return {}
                
                # Convertir a diccionario con información estructurada
                result = {
                    'sku': sku,
                    'total_forecasts': len(df),
                    'total_quantity': df['forecasted_quantity'].sum(),
                    'avg_quantity': df['forecasted_quantity'].mean(),
                    'forecasts_by_date': df.set_index('forecast_date')['forecasted_quantity'].to_dict(),
                    'summary': df.iloc[0].to_dict() if len(df) > 0 else {}
                }
                
                logger.success(f"Forecast obtenido para SKU {sku}", 
                             total_forecasts=result['total_forecasts'],
                             total_quantity=result['total_quantity'])
                
                return result
                
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo forecast para SKU {sku}: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo forecast para SKU {sku}: {e}")
            raise
    
    def get_available_months(self, year: Optional[int] = None) -> List[int]:
        """
        Obtener lista de meses disponibles en la tabla forecast.
        
        Args:
            year (Optional[int]): Año específico. Si es None, obtiene todos los meses de todos los años.
            
        Returns:
            List[int]: Lista de meses disponibles ordenados
        """
        # Usar año actual si no se especifica
        if year is None:
            logger.info("Obteniendo meses disponibles en forecast (todos los años)")
            query = """
            SELECT DISTINCT month 
            FROM forecast 
            ORDER BY month
            """
            params = ()
        else:
            logger.info(f"Obteniendo meses disponibles en forecast para el año {year}")
            query = """
            SELECT DISTINCT month 
            FROM forecast 
            WHERE year = %s
            ORDER BY month
            """
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
    
    def get_forecast_summary(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtener resumen general de todos los forecasts.
        
        Args:
            year (Optional[int]): Año específico. Si es None, obtiene resumen de todos los años.
            
        Returns:
            Dict[str, Any]: Resumen de estadísticas de forecast
        """
        # Usar año actual si no se especifica
        if year is None:
            logger.info("Obteniendo resumen general de forecasts (todos los años)")
            query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sku) as unique_skus,
                COUNT(DISTINCT month) as available_months,
                MIN(forecast_date) as earliest_date,
                MAX(forecast_date) as latest_date,
                SUM(forecasted_quantity) as total_forecasted_quantity,
                AVG(forecasted_quantity) as avg_forecasted_quantity,
                MIN(forecasted_quantity) as min_forecasted_quantity,
                MAX(forecasted_quantity) as max_forecasted_quantity
            FROM forecast
            """
            params = ()
        else:
            logger.info(f"Obteniendo resumen general de forecasts para el año {year}")
            query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sku) as unique_skus,
                COUNT(DISTINCT month) as available_months,
                MIN(forecast_date) as earliest_date,
                MAX(forecast_date) as latest_date,
                SUM(forecasted_quantity) as total_forecasted_quantity,
                AVG(forecasted_quantity) as avg_forecasted_quantity,
                MIN(forecasted_quantity) as min_forecasted_quantity,
                MAX(forecasted_quantity) as max_forecasted_quantity
            FROM forecast
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
                        'total_forecasted_quantity': float(result[5]) if result[5] else 0,
                        'avg_forecasted_quantity': float(result[6]) if result[6] else 0,
                        'min_forecasted_quantity': result[7],
                        'max_forecasted_quantity': result[8],
                        'year': year if year else "todos"
                    }
                    
                    logger.success("Resumen de forecasts obtenido exitosamente", **summary)
                    
                    return summary
                    
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos obteniendo resumen: {e}")
            raise Exception(f"Error de base de datos: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo resumen: {e}")
            raise


def get_forecasts_by_month(month: int, year: Optional[int] = None) -> Dict[str, float]:
    """
    Función de conveniencia para obtener forecasts por mes.
    
    Args:
        month (int): Número del mes (1-12)
        year (Optional[int]): Año específico. Si es None, usa el año actual.
        
    Returns:
        Dict[str, float]: Diccionario con SKU como clave y cantidad predicha como valor
    """
    reader = ForecastReader()
    return reader.get_forecasts_by_month(month, year)


# Script de ejemplo/testing
if __name__ == "__main__":
    import sys
    
    # Ejemplo de uso
    try:
        reader = ForecastReader()
        current_year = datetime.now().year
        
        # Mostrar resumen general
        print("\n📊 Resumen de Forecasts (Todos los años):")
        print("=" * 50)
        summary = reader.get_forecast_summary()
        for key, value in summary.items():
            print(f"   {key}: {value}")
        
        # Mostrar resumen del año actual
        print(f"\n📊 Resumen de Forecasts ({current_year}):")
        print("=" * 50)
        summary_current_year = reader.get_forecast_summary(current_year)
        for key, value in summary_current_year.items():
            print(f"   {key}: {value}")
        
        # Mostrar meses disponibles (todos los años)
        print("\n📅 Meses Disponibles (Todos los años):")
        print("=" * 50)
        months = reader.get_available_months()
        month_names = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                       'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        for month in months:
            print(f"   {month}: {month_names[month-1]}")
        
        # Mostrar meses disponibles del año actual
        print(f"\n📅 Meses Disponibles ({current_year}):")
        print("=" * 50)
        months_current_year = reader.get_available_months(current_year)
        for month in months_current_year:
            print(f"   {month}: {month_names[month-1]}")
        
        # Ejemplo: forecasts para enero (año actual)
        if 1 in months_current_year:
            print(f"\n📈 Ejemplo - Forecasts para Enero {current_year} (primeros 10):")
            print("=" * 50)
            january_forecasts = reader.get_forecasts_by_month(1, current_year)
            for i, (sku, quantity) in enumerate(list(january_forecasts.items())[:10]):
                print(f"   {sku}: {quantity:.1f} unidades")
            
            print(f"\n   Total SKUs en enero {current_year}: {len(january_forecasts)}")
            print(f"   Total unidades proyectadas: {sum(january_forecasts.values()):.1f}")
        
        # Ejemplo: forecasts para enero (sin especificar año - usa año actual)
        print(f"\n📈 Ejemplo - Forecasts para Enero (año por defecto - {current_year}):")
        print("=" * 50)
        january_forecasts_default = reader.get_forecasts_by_month(1)  # Sin especificar año
        print(f"   Total SKUs en enero (por defecto): {len(january_forecasts_default)}")
        print(f"   Total unidades proyectadas: {sum(january_forecasts_default.values()):.1f}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1) 