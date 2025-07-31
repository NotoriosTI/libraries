#!/usr/bin/env python3
"""
Script de Prueba - Sales Engine Database Client

Este script demuestra cómo usar el módulo db_client del sales-engine
para leer datos de la base de datos tanto local como en contenedor.

Funcionalidades demostradas:
- Conexión a la base de datos
- Lectura básica de datos
- Uso del QueryBuilder
- Agregaciones y resúmenes
- Consultas personalizadas

Uso:
    # Desde el directorio sales-engine
    python tests/test_db_client.py
    
    # Con variables de entorno personalizadas
    USE_TEST_ODOO=false python tests/test_db_client.py
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Agregar src al path para importar sales_engine
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Importar el módulo db_client
from sales_engine.db_client import DatabaseReader, QueryBuilder
from sales_engine.db_client.query_builder import (
    sales_by_date_range, 
    sales_by_customer,
    sales_summary_by_date,
    top_customers,
    top_products
)

def main():
    """Función principal que demuestra el uso del db_client."""
    
    print("🚀 Prueba de Uso - Sales Engine Database Client")
    print("=" * 60)
    
    # Configuración desde variables de entorno
    use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
    
    print(f"📋 Configuración:")
    print(f"   - Usar Test Odoo: {use_test_odoo}")
    print(f"   - Entorno: {os.getenv('ENVIRONMENT', 'local')}")
    print()
    
    try:
        # Crear cliente de base de datos
        print("📡 Inicializando DatabaseReader...")
        with DatabaseReader(use_test_odoo=use_test_odoo) as db_reader:
            
            # 1. Probar conexión
            print("\n1️⃣ Probando conexión a la base de datos...")
            if db_reader.test_connection():
                print("   ✅ Conexión exitosa")
            else:
                print("   ❌ Error de conexión")
                return
            
            # 2. Obtener información de la tabla
            print("\n2️⃣ Obteniendo información de la tabla...")
            table_info = db_reader.get_table_info()
            print(f"   📊 Total de registros: {table_info['total_records']:,}")
            print(f"   📅 Fecha mínima: {table_info['min_date']}")
            print(f"   📅 Fecha máxima: {table_info['max_date']}")
            print(f"   🏗️  Columnas: {len(table_info['columns'])}")
            
            # 3. Obtener datos recientes usando método directo
            print("\n3️⃣ Obteniendo ventas de los últimos 7 días (método directo)...")
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            recent_sales = db_reader.get_sales_data(
                start_date=start_date,
                end_date=end_date,
                limit=5
            )
            
            print(f"   📦 Registros encontrados: {len(recent_sales)}")
            if not recent_sales.empty:
                print("   📋 Primeros registros:")
                for idx, row in recent_sales.head(3).iterrows():
                    print(f"      • {row['issueddate']} | {row['customer_name']} | ${row['total_total']:,.0f}")
            
            # 4. Usar QueryBuilder - Consulta básica
            print("\n4️⃣ Usando QueryBuilder - Consulta básica...")
            qb = QueryBuilder()
            query, params = qb.select('*').where('total_total', '>', 100000).order_by_desc('issueddate').limit(3).build()
            
            print(f"   🔍 Query: {query}")
            print(f"   📝 Params: {params}")
            
            high_value_sales = db_reader.execute_custom_query(query, params)
            print(f"   💰 Ventas de alto valor encontradas: {len(high_value_sales)}")
            
            # 5. Usar funciones de conveniencia del QueryBuilder
            print("\n5️⃣ Usando funciones de conveniencia...")
            
            # Ventas por rango de fecha
            date_qb = sales_by_date_range(start_date, end_date)
            query, params = date_qb.limit(10).build()
            date_sales = db_reader.execute_custom_query(query, params)
            print(f"   📅 Ventas por fecha: {len(date_sales)} registros")
            
            # Top productos
            top_products_qb = top_products(5)
            query, params = top_products_qb.build()
            products_data = db_reader.execute_custom_query(query, params)
            print(f"   🏆 Top 5 productos:")
            for idx, row in products_data.iterrows():
                print(f"      • {row['items_product_sku']} | {row['items_product_description'][:30]}... | ${row['total_amount']:,.0f}")
            
            # 6. Obtener resumen agregado usando método directo
            print("\n6️⃣ Resumen de ventas por fecha (últimos 30 días)...")
            summary_start = end_date - timedelta(days=30)
            summary = db_reader.get_sales_summary(
                start_date=summary_start,
                end_date=end_date,
                group_by='date'
            )
            
            print(f"   📊 Días con ventas: {len(summary)}")
            if not summary.empty:
                total_amount = summary['total_amount'].sum()
                total_transactions = summary['total_transactions'].sum()
                print(f"   💵 Total ventas (30 días): ${total_amount:,.0f}")
                print(f"   🔢 Total transacciones: {total_transactions:,}")
                print(f"   📈 Promedio por día: ${total_amount/len(summary):,.0f}")
            
            # 7. QueryBuilder avanzado con múltiples condiciones
            print("\n7️⃣ QueryBuilder avanzado - Múltiples filtros...")
            
            # Buscar ventas específicas
            advanced_qb = QueryBuilder()
            advanced_qb.select('customer_name', 'items_product_description', 'total_total', 'issueddate') \
                     .where('total_total', '>=', 50000) \
                     .where('warehouse_name', '=', 'TIENDA') \
                     .where_date_range('issueddate', start_date=summary_start) \
                     .order_by_desc('total_total') \
                     .limit(5)
            
            query, params = advanced_qb.build()
            advanced_results = db_reader.execute_custom_query(query, params)
            
            print(f"   🎯 Ventas filtradas encontradas: {len(advanced_results)}")
            if not advanced_results.empty:
                print("   📋 Resultados:")
                for idx, row in advanced_results.iterrows():
                    print(f"      • {row['customer_name'][:20]}... | ${row['total_total']:,.0f} | {row['issueddate']}")
            
            # 8. Consulta personalizada con agregación
            print("\n8️⃣ Consulta personalizada - Ventas por mes...")
            
            custom_query = """
            SELECT 
                DATE_TRUNC('month', issueddate) as month,
                COUNT(*) as total_transactions,
                SUM(total_total) as total_amount,
                AVG(total_total) as avg_amount
            FROM sales_items 
            WHERE issueddate >= %s
            GROUP BY DATE_TRUNC('month', issueddate)
            ORDER BY month DESC
            LIMIT 6
            """
            
            monthly_summary = db_reader.execute_custom_query(
                custom_query, 
                [end_date - timedelta(days=180)]  # Últimos 6 meses
            )
            
            print(f"   📅 Resumen mensual:")
            for idx, row in monthly_summary.iterrows():
                month = row['month'].strftime('%Y-%m')
                print(f"      • {month} | {row['total_transactions']:,} trans | ${row['total_amount']:,.0f} | Prom: ${row['avg_amount']:,.0f}")
            
        print("\n✅ Prueba completada exitosamente!")
        print("\n📚 Funcionalidades probadas:")
        print("   - ✅ Conexión a base de datos (local/contenedor)")
        print("   - ✅ Lectura básica de datos con filtros")
        print("   - ✅ QueryBuilder fluido")
        print("   - ✅ Funciones de conveniencia")
        print("   - ✅ Agregaciones y resúmenes")
        print("   - ✅ Consultas personalizadas")
        print("   - ✅ Manejo automático de conexiones")
        
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


def print_usage_examples():
    """Imprimir ejemplos de uso para diferentes casos."""
    
    print("\n🔧 Ejemplos de Uso Avanzado")
    print("=" * 40)
    
    print("\n1. Uso Básico:")
    print("""
from sales_engine.db_client import DatabaseReader

with DatabaseReader() as db:
    # Obtener ventas recientes
    sales = db.get_sales_data(limit=100)
    print(f"Total: {len(sales)} registros")
""")
    
    print("\n2. QueryBuilder Fluido:")
    print("""
from sales_engine.db_client import QueryBuilder

qb = QueryBuilder()
query, params = qb.select('customer_name', 'total_total') \\
                  .where('total_total', '>', 50000) \\
                  .order_by_desc('total_total') \\
                  .limit(10) \\
                  .build()

with DatabaseReader() as db:
    results = db.execute_custom_query(query, params)
""")
    
    print("\n3. Funciones de Conveniencia:")
    print("""
from sales_engine.db_client.query_builder import top_customers
from datetime import date, timedelta

# Top clientes del último mes
start_date = date.today() - timedelta(days=30)
qb = top_customers(10).where_date_range('issueddate', start_date)

with DatabaseReader() as db:
    top_clients = db.execute_custom_query(*qb.build())
""")
    
    print("\n4. Uso en Contenedor (docker-compose):")
    print("""
# docker-compose.yml
services:
  app:
    environment:
      - USE_TEST_ODOO=false
      - DB_HOST=127.0.0.1  # Para proxy compartido
      - DB_PORT=5432
""")


def test_connection_only():
    """Función para probar solo la conexión."""
    print("🔍 Modo: Solo prueba de conexión")
    use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
    
    try:
        with DatabaseReader(use_test_odoo=use_test_odoo) as db:
            if db.test_connection():
                print("✅ Conexión exitosa")
                return 0
            else:
                print("❌ Error de conexión")
                return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sales Engine DB Client Test")
    parser.add_argument("--examples", action="store_true", 
                      help="Mostrar ejemplos de uso avanzado")
    parser.add_argument("--test-only", action="store_true",
                      help="Solo probar conexión")
    
    args = parser.parse_args()
    
    if args.examples:
        print_usage_examples()
        sys.exit(0)
    
    if args.test_only:
        exit_code = test_connection_only()
        sys.exit(exit_code)
    
    # Ejecutar prueba completa
    exit_code = main()
    sys.exit(exit_code) 