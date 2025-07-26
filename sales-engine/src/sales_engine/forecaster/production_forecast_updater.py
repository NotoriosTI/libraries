#!/usr/bin/env python3
"""
Production Forecast Database Updater

Este módulo proporciona funcionalidades para gestionar la tabla production_forecast
que almacena los resultados de los cálculos de producción basados en forecasts,
ventas actuales e inventario disponible.

Implementa:
- 💾 Inserción/actualización de datos de production_forecast
- 🗄️ Gestión automática de la estructura de la tabla
- 📊 Procesamiento en lotes para eficiencia
- 🔄 Upsert para evitar duplicados
- ⏰ Timestamps automáticos para auditoría
- 🏭 Cálculo completo de producción requerida

Author: Bastian Ibañez
"""

import sys
import os
from pathlib import Path
import pandas as pd
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from typing import Dict, Any, Optional
import structlog
from datetime import datetime, date
from calendar import monthrange

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_manager import secrets

# Configurar logger
logger = structlog.get_logger(__name__)

# ============================================================================
# CONSTANTES DE CONFIGURACIÓN
# ============================================================================

# Lista de SKUs a ignorar en los cálculos de producción
IGNORE_SKU = [
    6889, # Starken
    6911, # Bluexpress
    6912, # Recibelo domicilio
]


class ProductionForecastUpdater:
    """
    Maneja la inserción/actualización de datos de production_forecast en la base de datos.
    
    Esta clase sigue el patrón de DatabaseUpdater del sales-engine para mantener
    consistencia en el manejo de conexiones y transacciones.
    """
    
    def __init__(self):
        """Inicializar el updater de production forecasts."""
        self.config = secrets
        self.logger = logger.bind(component="production_forecast_updater")
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        
        self.logger.info(
            "ProductionForecastUpdater inicializado",
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
    
    def ensure_table_exists(self):
        """Crear tabla production_forecast si no existe."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS production_forecast (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            product_name TEXT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            month_name VARCHAR(20) NOT NULL,
            forecast_quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
            current_sales DECIMAL(10,2) NOT NULL DEFAULT 0,
            inventory_available DECIMAL(10,2) NOT NULL DEFAULT 0,
            production_needed DECIMAL(10,2) NOT NULL,
            priority VARCHAR(10) NOT NULL CHECK (priority IN ('ALTA', 'MEDIA', 'BAJA')),
            is_valid_product BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraint único por SKU, año y mes
            UNIQUE(sku, year, month)
        );
        """
        
        # Crear función trigger para updated_at
        create_trigger_function_sql = """
        CREATE OR REPLACE FUNCTION update_production_forecast_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
        
        # Crear trigger
        create_trigger_sql = """
        DROP TRIGGER IF EXISTS update_production_forecast_updated_at ON production_forecast;
        CREATE TRIGGER update_production_forecast_updated_at
            BEFORE UPDATE ON production_forecast
            FOR EACH ROW EXECUTE FUNCTION update_production_forecast_updated_at_column();
        """
        
        # Crear índices
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_date ON production_forecast (year, month);",
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_sku ON production_forecast (sku);",
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_priority ON production_forecast (priority);",
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_production_needed ON production_forecast (production_needed DESC);",
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_created_at ON production_forecast (created_at);",
            "CREATE INDEX IF NOT EXISTS idx_production_forecast_valid_products ON production_forecast (is_valid_product);"
        ]
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Crear tabla
                    cursor.execute(create_table_sql)
                    self.logger.info("Tabla production_forecast verificada/creada")
                    
                    # Crear función trigger
                    cursor.execute(create_trigger_function_sql)
                    
                    # Crear trigger
                    cursor.execute(create_trigger_sql)
                    
                    # Crear índices
                    for index_sql in create_indexes_sql:
                        cursor.execute(index_sql)
                    
                    self.logger.info("Tabla production_forecast y estructuras auxiliares creadas exitosamente")
                    
        except Exception as e:
            self.logger.error("Error creando tabla production_forecast", error=str(e))
            raise Exception(f"Error creando tabla production_forecast: {str(e)}") from e
    
    def upsert_production_data(self, df: pd.DataFrame, year: int, month: int) -> Dict[str, int]:
        """
        Insertar o actualizar datos de production_forecast usando UPSERT.
        
        Args:
            df: DataFrame con datos de producción (debe incluir solo productos válidos)
            year: Año del cálculo
            month: Mes del cálculo
            
        Returns:
            Dict con contadores de registros insertados/actualizados
        """
        self.ensure_table_exists()
        
        # Validar DataFrame
        required_columns = ['sku', 'product_name', 'forecast', 'current_sales', 'inventory', 'production_needed', 'priority']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"DataFrame falta columnas requeridas: {missing_columns}")
        
        # Agregar campos de fecha
        month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                       'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        df_with_dates = df.copy()
        df_with_dates['year'] = year
        df_with_dates['month'] = month
        df_with_dates['month_name'] = month_names[month] if 1 <= month <= 12 else f"Mes_{month}"
        df_with_dates['is_valid_product'] = True  # Solo productos válidos llegan aquí
        
        upsert_sql = """
        INSERT INTO production_forecast (
            sku, product_name, year, month, month_name,
            forecast_quantity, current_sales, inventory_available,
            production_needed, priority, is_valid_product
        ) VALUES (
            %(sku)s, %(product_name)s, %(year)s, %(month)s, %(month_name)s,
            %(forecast)s, %(current_sales)s, %(inventory)s,
            %(production_needed)s, %(priority)s, %(is_valid_product)s
        )
        ON CONFLICT (sku, year, month) 
        DO UPDATE SET
            product_name = EXCLUDED.product_name,
            month_name = EXCLUDED.month_name,
            forecast_quantity = EXCLUDED.forecast_quantity,
            current_sales = EXCLUDED.current_sales,
            inventory_available = EXCLUDED.inventory_available,
            production_needed = EXCLUDED.production_needed,
            priority = EXCLUDED.priority,
            is_valid_product = EXCLUDED.is_valid_product,
            updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Convertir DataFrame a lista de diccionarios
                    records = df_with_dates.to_dict('records')
                    
                    # Validar que no haya registros vacíos
                    if not records:
                        self.logger.warning("No hay registros para procesar")
                        return {'total_processed': 0, 'records_this_month': 0, 'total_records_in_db': 0}
                    
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
                    cursor.execute(
                        "SELECT COUNT(*) FROM production_forecast WHERE year = %s AND month = %s", 
                        (year, month)
                    )
                    records_this_month = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM production_forecast")
                    total_records = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(DISTINCT sku) FROM production_forecast WHERE year = %s AND month = %s", (year, month))
                    unique_skus_this_month = cursor.fetchone()[0]
                    
                    result = {
                        'total_processed': total_processed,
                        'records_this_month': records_this_month,
                        'total_records_in_db': total_records,
                        'unique_skus_this_month': unique_skus_this_month
                    }
                    
                    self.logger.info(
                        "Production forecast guardado en base de datos exitosamente",
                        **result
                    )
                    
                    return result
                    
        except Exception as e:
            self.logger.error("Error guardando production forecast en base de datos", error=str(e))
            raise Exception(f"Error guardando production forecast: {str(e)}") from e
    
    def get_production_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        Obtener resumen de production forecast para un mes específico.
        
        Args:
            year: Año
            month: Mes
            
        Returns:
            Dict con resumen de estadísticas
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    
                    # Estadísticas generales
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_products,
                            SUM(forecast_quantity) as total_forecast,
                            SUM(current_sales) as total_sales,
                            SUM(inventory_available) as total_inventory,
                            SUM(production_needed) as total_production_needed,
                            COUNT(CASE WHEN production_needed > 0 THEN 1 END) as products_need_production,
                            COUNT(CASE WHEN production_needed < -10 THEN 1 END) as products_excess_inventory
                        FROM production_forecast 
                        WHERE year = %s AND month = %s AND is_valid_product = TRUE
                    """, (year, month))
                    
                    general_stats = cursor.fetchone()
                    
                    # Estadísticas por prioridad
                    cursor.execute("""
                        SELECT 
                            priority,
                            COUNT(*) as count,
                            SUM(production_needed) as total_needed
                        FROM production_forecast 
                        WHERE year = %s AND month = %s AND is_valid_product = TRUE AND production_needed > 0
                        GROUP BY priority
                        ORDER BY 
                            CASE priority 
                                WHEN 'ALTA' THEN 1 
                                WHEN 'MEDIA' THEN 2 
                                WHEN 'BAJA' THEN 3 
                            END
                    """, (year, month))
                    
                    priority_stats = cursor.fetchall()
                    
                    return {
                        'general': dict(general_stats) if general_stats else {},
                        'by_priority': [dict(row) for row in priority_stats],
                        'year': year,
                        'month': month
                    }
                    
        except Exception as e:
            self.logger.error("Error obteniendo resumen de production forecast", error=str(e))
            raise Exception(f"Error obteniendo resumen: {str(e)}") from e
    
    def cleanup_old_data(self, keep_months: int = 12) -> int:
        """
        Limpiar datos antiguos, manteniendo solo los últimos N meses.
        
        Args:
            keep_months: Número de meses a mantener
            
        Returns:
            Número de registros eliminados
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    
                    # Calcular fecha límite
                    cursor.execute("""
                        DELETE FROM production_forecast 
                        WHERE (year * 12 + month) < (
                            SELECT MAX(year * 12 + month) - %s 
                            FROM production_forecast
                        )
                    """, (keep_months,))
                    
                    deleted_count = cursor.rowcount
                    
                    self.logger.info(f"Limpieza completada", deleted_records=deleted_count, months_kept=keep_months)
                    
                    return deleted_count
                    
        except Exception as e:
            self.logger.error("Error en limpieza de datos", error=str(e))
            raise Exception(f"Error en limpieza: {str(e)}") from e


# Función de conveniencia para uso directo
def save_production_forecast(df: pd.DataFrame, year: int, month: int) -> Dict[str, int]:
    """
    Función de conveniencia para guardar production forecast.
    
    Args:
        df: DataFrame con datos de producción
        year: Año del cálculo
        month: Mes del cálculo
        
    Returns:
        Dict con estadísticas de la operación
    """
    updater = ProductionForecastUpdater()
    return updater.upsert_production_data(df, year, month)


# ============================================================================
# FUNCIONES PARA CÁLCULO COMPLETO DE PRODUCCIÓN (como test_production_calculation)
# ============================================================================

def get_forecasts_by_month(month: int) -> Dict[str, float]:
    """
    Obtener forecasts para un mes específico desde la base de datos.
    
    Args:
        month: Mes (1-12)
        
    Returns:
        Dict con SKU -> forecast_quantity
    """
    try:
        # Importar aquí para evitar dependencias circulares
        from sales_engine.db_client import get_forecasts_by_month as get_forecasts
        
        # Obtener fecha actual para el año
        current_year = datetime.now().year
        
        # Calcular fecha del forecast (próximo mes)
        if month == 12:
            forecast_year = current_year + 1
            forecast_month = 1
        else:
            forecast_year = current_year
            forecast_month = month + 1
        
        # Obtener forecasts del mes específico
        forecasts = get_forecasts(forecast_month)
        
        return forecasts
        
    except Exception as e:
        print(f"❌ Error obteniendo forecasts: {e}")
        return {}


def get_sales_by_month(year: int, month: int) -> pd.DataFrame:
    """
    Obtener ventas de todos los SKUs para un mes específico.
    
    Args:
        year: Año (ej: 2024)
        month: Mes (1-12)
    
    Returns:
        pd.DataFrame: Datos de ventas del mes
    """
    try:
        # Importar aquí para evitar dependencias circulares
        from sales_engine.db_client import DatabaseReader
        
        # Calcular primer y último día del mes
        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        
        print(f"📅 Obteniendo ventas desde {start_date} hasta {end_date}")
        
        reader = DatabaseReader()
        
        return reader.get_sales_data(
            start_date=start_date,
            end_date=end_date
        )
        
    except Exception as e:
        print(f"❌ Error obteniendo ventas: {e}")
        return pd.DataFrame()


def get_inventory_from_odoo(skus: list, use_test_odoo: bool = False) -> Dict[str, Dict]:
    """
    Obtener inventario desde Odoo para una lista de SKUs.
    
    Args:
        skus: Lista de SKUs a consultar
        use_test_odoo: Si usar entorno de test
        
    Returns:
        Dict con SKU -> info de inventario
    """
    try:
        # Importar aquí para evitar dependencias circulares
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "odoo-api" / "src"))
        from odoo_api.warehouses import OdooWarehouse
        
        # Obtener configuración de Odoo
        odoo_config = secrets.get_odoo_config(use_test=use_test_odoo)
        odoo_warehouse = OdooWarehouse(
            db=odoo_config['db'],
            url=odoo_config['url'],
            username=odoo_config['username'],
            password=odoo_config['password']
        )
        
        # Obtener inventario para todos los SKUs (usar batch para eficiencia)
        inventory_data = {}
        batch_size = 50  # Procesar en lotes para evitar timeouts
        
        for i in range(0, len(skus), batch_size):
            batch_skus = skus[i:i+batch_size]
            try:
                batch_inventory = odoo_warehouse.get_stock_by_sku(batch_skus)
                inventory_data.update(batch_inventory)
                print(f"   Procesado lote {i//batch_size + 1}/{(len(skus)-1)//batch_size + 1}")
            except Exception as e:
                print(f"   ⚠️  Error en lote {i//batch_size + 1}: {e}")
                # Continuar con el siguiente lote
                continue
        
        return inventory_data
        
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        print("💡 Nota: Se requiere configuración de Odoo en config_manager")
        return {}


def calculate_production_quantities(year: int = None, month: int = None, use_test_odoo: bool = False) -> pd.DataFrame:
    """
    Calcular la cantidad a producir por SKU basado en:
    Cantidad a producir = Forecast - Ventas del mes actual - Inventario actual
    
    Args:
        year: Año (por defecto usa el año actual)
        month: Mes (por defecto usa el mes actual)
        use_test_odoo: Si usar el entorno de test de Odoo (por defecto False)
    
    Returns:
        pd.DataFrame: Datos de producción requerida por SKU
    """
    # Usar fecha actual si no se especifica
    if year is None or month is None:
        current_date = datetime.now()
        year = year or current_date.year
        month = month or current_date.month
    
    month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    print(f"\n🏭 CÁLCULO DE PRODUCCIÓN REQUERIDA - {month_names[month]} {year}")
    print("=" * 70)
    
    try:
        # 1. Obtener forecasts del mes
        print(f"📈 Obteniendo forecasts para {month_names[month]}...")
        forecasts = get_forecasts_by_month(month)
        if not forecasts:
            print("❌ No se encontraron forecasts para el mes especificado")
            return None
        
        # 2. Obtener ventas del mes actual
        print(f"📊 Obteniendo ventas de {month_names[month]} {year}...")
        sales_data = get_sales_by_month(year, month)
        
        if sales_data.empty or 'items_quantity' not in sales_data.columns:
            print("❌ No se encontraron datos de ventas válidos")
            return None
        
        sales_by_sku = sales_data.groupby('items_product_sku')['items_quantity'].sum()
        
        # 3. Obtener inventario actual desde Odoo
        print(f"📦 Obteniendo inventario actual desde Odoo...")
        
        # Obtener todos los SKUs únicos de forecasts y ventas
        all_skus = list(set(forecasts.keys()) | set(sales_by_sku.index))
        
        # Filtrar SKUs ignorados
        if IGNORE_SKU:
            original_count = len(all_skus)
            # Convertir SKUs ignorados a strings para comparación
            ignore_skus_str = [str(sku) for sku in IGNORE_SKU]
            all_skus = [sku for sku in all_skus if str(sku) not in ignore_skus_str]
            ignored_count = original_count - len(all_skus)
            print(f"   🔍 Filtrando SKUs ignorados: {ignored_count} SKUs excluidos")
            print(f"   📋 SKUs ignorados: {', '.join(str(sku) for sku in IGNORE_SKU)}")
        
        print(f"   Consultando inventario para {len(all_skus)} SKUs...")
        
        inventory_data = get_inventory_from_odoo(all_skus, use_test_odoo)
        
        # 4. Crear DataFrame de análisis
        print(f"🔢 Calculando cantidades de producción...")
        
        production_data = []
        for sku in all_skus:
            forecast_qty = forecasts.get(sku, 0)
            sales_qty = sales_by_sku.get(sku, 0)
            
            # Obtener inventario disponible
            inventory_info = inventory_data.get(sku, {})
            if inventory_info.get('found', False):
                inventory_qty = inventory_info.get('qty_available', 0)
                product_name = inventory_info.get('product_name', 'Sin nombre')
            else:
                inventory_qty = 0
                product_name = 'Producto no encontrado en Odoo'
            
            # Calcular cantidad a producir
            production_qty = forecast_qty - sales_qty - inventory_qty
            
            production_data.append({
                'sku': sku,
                'product_name': product_name,
                'forecast': forecast_qty,
                'current_sales': sales_qty,
                'inventory': inventory_qty,
                'production_needed': production_qty,
                'priority': 'ALTA' if production_qty > 100 else 'MEDIA' if production_qty > 20 else 'BAJA'
            })
        
        # Crear DataFrame inicial
        df_all_products = pd.DataFrame(production_data)
        
        # Filtrar productos no encontrados en Odoo
        print(f"🔍 Filtrando productos...")
        products_not_found = df_all_products[df_all_products['product_name'] == 'Producto no encontrado en Odoo']
        df_production = df_all_products[df_all_products['product_name'] != 'Producto no encontrado en Odoo'].copy()
        
        # Mostrar estadísticas de filtrado
        print(f"   📊 Total productos analizados: {len(df_all_products)}")
        print(f"   ✅ Productos válidos (encontrados en Odoo): {len(df_production)}")
        print(f"   ❌ Productos excluidos (no encontrados en Odoo): {len(products_not_found)}")
        
        # Mostrar información sobre SKUs ignorados
        if IGNORE_SKU:
            # Convertir SKUs ignorados a strings para búsqueda
            ignore_skus_str = [str(sku) for sku in IGNORE_SKU]
            ignored_forecast = sum(forecasts.get(str(sku), 0) for sku in IGNORE_SKU if str(sku) in forecasts)
            ignored_sales = sum(sales_by_sku.get(str(sku), 0) for sku in IGNORE_SKU if str(sku) in sales_by_sku.index)
            print(f"   🚫 SKUs ignorados por configuración: {len(IGNORE_SKU)}")
            print(f"   📈 Forecast ignorado: {ignored_forecast:,.0f} unidades")
            print(f"   📊 Ventas ignoradas: {ignored_sales:,.0f} unidades")
        
        if len(products_not_found) > 0:
            excluded_forecast = products_not_found['forecast'].sum()
            excluded_sales = products_not_found['current_sales'].sum()
            print(f"   📈 Forecast excluido: {excluded_forecast:,.0f} unidades")
            print(f"   📊 Ventas excluidas: {excluded_sales:,.0f} unidades")
        
        # Ordenar por cantidad de producción requerida
        df_production = df_production.sort_values('production_needed', ascending=False)
        
        # 5. Mostrar resultados (solo productos válidos)
        print(f"\n📋 RESUMEN DE PRODUCCIÓN (Solo productos válidos):")
        print("-" * 70)
        
        total_forecast = df_production['forecast'].sum()
        total_sales = df_production['current_sales'].sum()
        total_inventory = df_production['inventory'].sum()
        total_production = df_production['production_needed'].sum()
        
        print(f"   Total Forecast: {total_forecast:,.1f} unidades")
        print(f"   Total Ventas del mes: {total_sales:,.1f} unidades")
        print(f"   Total Inventario actual: {total_inventory:,.1f} unidades")
        print(f"   Total Producción requerida: {total_production:,.1f} unidades")
        
        # Productos que requieren producción urgente
        urgent_production = df_production[df_production['production_needed'] > 0]
        
        if not urgent_production.empty:
            print(f"\n🚨 TOP 15 PRODUCTOS REQUIEREN PRODUCCIÓN:")
            print("-" * 90)
            print(f"{'SKU':<12} {'Forecast':<10} {'Ventas':<8} {'Stock':<8} {'Producir':<10} {'Prioridad':<10}")
            print("-" * 90)
            
            for _, row in urgent_production.head(15).iterrows():
                print(f"{row['sku']:<12} {row['forecast']:<10.1f} {row['current_sales']:<8.1f} "
                      f"{row['inventory']:<8.1f} {row['production_needed']:<10.1f} {row['priority']:<10}")
        
        # Productos con exceso de inventario
        excess_inventory = df_production[df_production['production_needed'] < -10]
        
        if not excess_inventory.empty:
            print(f"\n📦 PRODUCTOS CON EXCESO DE INVENTARIO:")
            print("-" * 90)
            print(f"{'SKU':<12} {'Forecast':<10} {'Ventas':<8} {'Stock':<8} {'Exceso':<10}")
            print("-" * 90)
            
            for _, row in excess_inventory.head(10).iterrows():
                excess = abs(row['production_needed'])
                print(f"{row['sku']:<12} {row['forecast']:<10.1f} {row['current_sales']:<8.1f} "
                      f"{row['inventory']:<8.1f} {excess:<10.1f}")
        
        # Estadísticas por prioridad
        priority_stats = df_production[df_production['production_needed'] > 0].groupby('priority').agg({
            'production_needed': ['count', 'sum']
        }).round(1)
        
        if not priority_stats.empty:
            print(f"\n📊 ESTADÍSTICAS POR PRIORIDAD:")
            print("-" * 40)
            for priority in ['ALTA', 'MEDIA', 'BAJA']:
                if priority in priority_stats.index:
                    count = priority_stats.loc[priority, ('production_needed', 'count')]
                    total = priority_stats.loc[priority, ('production_needed', 'sum')]
                    print(f"   {priority:<6}: {count:3.0f} productos, {total:8,.1f} unidades")
        
        return df_production
        
    except Exception as e:
        print(f"❌ Error calculando producción: {e}")
        return None


def save_to_database(production_df: pd.DataFrame, year: int, month: int) -> bool:
    """
    Guardar resultados de production calculation en base de datos.
    
    Args:
        production_df: DataFrame con resultados de producción
        year: Año del cálculo
        month: Mes del cálculo
        
    Returns:
        bool: True si se guardó exitosamente
    """
    try:
        print(f"\n💾 Guardando resultados en base de datos...")
        
        result = save_production_forecast(production_df, year, month)
        
        print(f"✅ Datos guardados exitosamente:")
        print(f"   📊 Registros procesados: {result['total_processed']:,}")
        print(f"   📅 Registros para {month}/{year}: {result['records_this_month']:,}")
        print(f"   🗄️  Total registros en DB: {result['total_records_in_db']:,}")
        print(f"   📦 SKUs únicos este mes: {result['unique_skus_this_month']:,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error guardando en base de datos: {e}")
        return False


def main():
    """Función principal para calcular producción (como test_production_calculation)."""
    
    print("🏭 Herramienta de Cálculo de Producción (Actualizada)")
    print("=" * 60)
    
    # Usar fecha actual
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    print(f"\n📅 Calculando para {month_names[current_month]} {current_year}...")
    print(f"💡 Usando forecasts generados con validación de ciclo de vida")
    
    try:
        production_df = calculate_production_quantities(
            year=current_year, 
            month=current_month, 
            use_test_odoo=False
        )
        
        if production_df is not None:
            print(f"\n✅ Cálculo completado exitosamente!")
            print(f"   📊 Total productos válidos procesados: {len(production_df)}")
            print(f"   💡 Productos 'no encontrados en Odoo' fueron excluidos automáticamente")
            
            # Mostrar información sobre SKUs ignorados
            if IGNORE_SKU:
                print(f"   🚫 SKUs ignorados por configuración: {len(IGNORE_SKU)}")
                print(f"   📋 Lista de SKUs ignorados: {', '.join(str(sku) for sku in IGNORE_SKU)}")
            
            # Productos que requieren producción
            need_production = production_df[production_df['production_needed'] > 0]
            print(f"   🏭 Productos que requieren producción: {len(need_production)}")
            
            if not need_production.empty:
                total_to_produce = need_production['production_needed'].sum()
                print(f"   📈 Total unidades a producir: {total_to_produce:,.0f}")
                
                # Mostrar estadísticas por prioridad
                priority_stats = need_production.groupby('priority')['production_needed'].agg(['count', 'sum'])
                print(f"\n   📋 Resumen por prioridad:")
                for priority in ['ALTA', 'MEDIA', 'BAJA']:
                    if priority in priority_stats.index:
                        count = priority_stats.loc[priority, 'count']
                        total = priority_stats.loc[priority, 'sum']
                        print(f"      {priority:<6}: {count:3.0f} productos ({total:8,.0f} unidades)")
            
            # Productos con exceso de inventario
            excess_inventory = production_df[production_df['production_needed'] < -10]
            print(f"   📦 Productos con exceso de inventario: {len(excess_inventory)}")
            
            if not excess_inventory.empty:
                total_excess = abs(excess_inventory['production_needed'].sum())
                print(f"   📉 Total exceso de inventario: {total_excess:,.0f} unidades")
            
            # Guardar en base de datos
            db_saved = save_to_database(production_df, current_year, current_month)
            
            # Exportar resultados CSV (opcional)
            output_file = f"production_calculation_{current_year}_{current_month:02d}.csv"
            try:
                production_df.to_csv(output_file, index=False)
                print(f"\n💾 Resultados exportados a: {output_file}")
                print(f"   📝 Archivo contiene solo productos encontrados en Odoo")
            except Exception as e:
                print(f"\n⚠️  No se pudo exportar archivo CSV: {e}")
            
            if db_saved:
                print(f"\n🗄️  Datos también disponibles en tabla 'production_forecast'")
                print(f"   📊 Consulta ejemplo:")
                print(f"      SELECT * FROM production_forecast")
                print(f"      WHERE year = {current_year} AND month = {current_month}")
                print(f"      ORDER BY production_needed DESC;")
            
        else:
            print("\n❌ Error en el cálculo de producción")
            print("💡 Verifica que:")
            print("   - Existan forecasts generados para el mes actual")
            print("   - La conexión a Odoo esté funcionando")
            print("   - Los datos de ventas estén disponibles")
            print("   - Los productos tengan registros válidos en Odoo")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 