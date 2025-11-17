"""
DatabaseReader Simplificado para Sales Engine

Cliente de lectura de base de datos simplificado.
"""


import os
import pandas as pd
import psycopg2
import psycopg2.pool
from datetime import date
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("sales-engine-reader")
except ImportError:
    class LoggerFallback:
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
    logger = LoggerFallback()

try:
    from env_manager import get_config
except ImportError:
    print("⚠️  env_manager no disponible, usando solo variables de entorno")
    get_config = None


class DatabaseReader:
    """Cliente simplificado para leer datos de la base de datos de ventas."""
    
    def __init__(self, use_test_odoo: bool = False):
        self.use_test_odoo = use_test_odoo
        self.logger = logger
        self._connection_pool = None
        

        environment = os.getenv('ENVIRONMENT', 'local')
        if get_config is not None:
            try:
                environment = get_config("ENVIRONMENT")
            except Exception:
                pass

        logger.info(
            "DatabaseReader inicializado",
            environment=environment,
            use_test_odoo=use_test_odoo,
            component="sales_database_reader"
        )
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Obtener parámetros de conexión."""
        if get_config is not None:
            try:
                host = get_config("DB_HOST")
                port = int(get_config("DB_PORT"))
                database = get_config("DB_NAME")
                user = get_config("DB_USER")
                password = get_config("DB_PASSWORD")

                return {
                    'host': host,
                    'port': port,
                    'database': database,
                    'user': user,
                    'password': password
                }
            except Exception as e:
                logger.error("No se pudo obtener configuración de DB desde env_manager, usando variables de entorno",
                error=str(e),
                component="sales_database_reader")
        
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
                       component="sales_database_reader")
        
        conn = self._connection_pool.getconn()
        try:
            yield conn
        finally:
            self._connection_pool.putconn(conn)
    
    def test_connection(self) -> bool:
        """Probar conectividad de base de datos."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    result = cursor.fetchone()
                    logger.success("Prueba de conexión de base de datos exitosa",
                                 version=result[0] if result else "Desconocido")
                    return True
        except Exception as e:
            logger.error("Prueba de conexión falló", error=str(e))
            return False
    
    def get_sales_data(self, start_date: Optional[date] = None, end_date: Optional[date] = None,
                      customer_ids: Optional[List[int]] = None, product_skus: Optional[List[str]] = None,
                      limit: Optional[int] = None) -> pd.DataFrame:
        """Obtener datos de ventas con filtros opcionales."""
        try:
            query = "SELECT * FROM sales_items WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND issueddate >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND issueddate <= %s"
                params.append(end_date)
            
            if customer_ids:
                placeholders = ','.join(['%s'] * len(customer_ids))
                query += f" AND customer_customerid IN ({placeholders})"
                params.extend(customer_ids)
            
            if product_skus:
                placeholders = ','.join(['%s'] * len(product_skus))
                query += f" AND items_product_sku IN ({placeholders})"
                params.extend(product_skus)
            
            query += " ORDER BY issueddate DESC"
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            with self.get_connection() as conn:
                # Usar directamente psycopg2 para evitar problemas de parámetros
                df = pd.read_sql_query(query, conn, params=params)
            
            logger.info("Datos de ventas obtenidos exitosamente",
                       records_count=len(df),
                       start_date=str(start_date) if start_date else "Sin filtro",
                       end_date=str(end_date) if end_date else "Sin filtro")
            
            return df
            
        except Exception as e:
            logger.error("Error al obtener datos de ventas", error=str(e))
            raise
    
    def get_sales_summary(self, start_date: Optional[date] = None, end_date: Optional[date] = None,
                         group_by: str = 'date') -> pd.DataFrame:
        """Obtener resumen agregado de datos de ventas."""
        try:
            group_fields = {
                'date': ['issueddate'],
                'customer': ['customer_customerid', 'customer_name'],
                'product': ['items_product_sku', 'items_product_description'],
                'warehouse': ['warehouse_name'],
                'channel': ['sales_channel']
            }
            
            if group_by not in group_fields:
                raise ValueError(f"group_by debe ser uno de: {list(group_fields.keys())}")
            
            fields = group_fields[group_by]
            select_fields = ', '.join(fields)
            group_fields_str = ', '.join(fields)
            
            query = f"""
            SELECT 
                {select_fields},
                COUNT(*) as total_transactions,
                SUM(items_quantity) as total_quantity,
                SUM(totals_net) as total_net,
                SUM(totals_vat) as total_vat,
                SUM(total_total) as total_amount,
                AVG(items_unitprice) as avg_unit_price
            FROM sales_items
            WHERE 1=1
            """
            
            params = []
            
            if start_date:
                query += " AND issueddate >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND issueddate <= %s"
                params.append(end_date)
            
            query += f" GROUP BY {group_fields_str}"
            query += f" ORDER BY {fields[0]} DESC"
            
            with self.get_connection() as conn:
                # Usar directamente psycopg2 para evitar problemas de parámetros
                df = pd.read_sql_query(query, conn, params=params)
            
            logger.info("Resumen de ventas obtenido exitosamente",
                       records_count=len(df), group_by=group_by)
            
            return df
            
        except Exception as e:
            logger.error("Error al obtener resumen de ventas", error=str(e))
            raise
    
    def execute_custom_query(self, query: str, params: Optional[List] = None) -> pd.DataFrame:
        """Ejecutar consulta SQL personalizada."""
        try:
            with self.get_connection() as conn:
                # Usar directamente psycopg2 para evitar problemas de parámetros
                df = pd.read_sql_query(query, conn, params=params or [])
            
            logger.info("Consulta personalizada ejecutada exitosamente",
                       records_count=len(df))
            
            return df
            
        except Exception as e:
            logger.error("Error al ejecutar consulta personalizada",
                        error=str(e), query=query[:100])
            raise
    
    def get_table_info(self, table_name: str = 'sales_items') -> Dict[str, Any]:
        """Obtener información sobre una tabla."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Información de columnas
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns 
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, [table_name])
                    columns = [dict(zip([desc[0] for desc in cursor.description], row)) 
                              for row in cursor.fetchall()]
                    
                    # Conteo de registros
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    total_records = cursor.fetchone()[0]
                    
                    # Fechas min/max
                    cursor.execute(f"""
                        SELECT MIN(issueddate) as min_date, MAX(issueddate) as max_date
                        FROM {table_name}
                    """)
                    date_result = cursor.fetchone()
            
            info = {
                'table_name': table_name,
                'total_records': total_records,
                'columns': columns,
                'min_date': date_result[0] if date_result else None,
                'max_date': date_result[1] if date_result else None
            }
            
            logger.info("Información de tabla obtenida exitosamente",
                       table_name=table_name, total_records=total_records)
            
            return info
            
        except Exception as e:
            logger.error("Error al obtener información de tabla", error=str(e))
            raise
    
    def close(self):
        """Cerrar pool de conexiones."""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("Pool de conexiones de base de datos cerrado")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 