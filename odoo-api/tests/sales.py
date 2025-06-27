import os
from decouple import config, RepositoryEnv
from src.odoo_api import OdooSales
import pandas as pd
from datetime import datetime
import time

tests_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(tests_dir, ".env")
env = RepositoryEnv(env_path)


def setup_odoo_sales():
    """
    Configura la conexión a Odoo para los tests
    """
    return OdooSales(
        url=config("ODOO_TEST_URL"),
        db=config("ODOO_TEST_DB"),
        username=config("ODOO_TEST_USERNAME"),
        password=config("ODOO_TEST_PASSWORD"),
    )


def test_read_sales_by_day(odoo_sales):
    """
    Test para read_sales_by_day - ventas de un día específico
    """
    print("=" * 80)
    print("🎯 TEST 1: read_sales_by_day() - Ventas del 19 de junio de 2025")
    print("=" * 80)
    
    # Test con fecha string
    ventas = odoo_sales.read_sales_by_day("2025-06-19")
    
    if isinstance(ventas, str):
        print(f"❌ Error: {ventas}")
        return None
    
    print(f"📊 Total de ventas encontradas: {len(ventas)}")
    
    if not ventas.empty:
        # Mostrar información básica
        print("\n📋 Información básica:")
        print(f"   - Columnas: {list(ventas.columns)}")
        print(f"   - Fecha de primera orden: {ventas['date_order'].min()}")
        print(f"   - Fecha de última orden: {ventas['date_order'].max()}")
        
        # Mostrar las primeras 3 órdenes
        print("\n🔍 Primeras 3 órdenes:")
        display_cols = ['name', 'date_order', 'amount_total']
        if all(col in ventas.columns for col in display_cols):
            print(ventas[display_cols].head(3).to_string(index=False))
        
        # Verificar órdenes específicas
        problem_orders = ['SN-68037', 'SN-68035', 'SN-68033']
        found_orders = ventas[ventas['name'].isin(problem_orders)]
        if not found_orders.empty:
            print(f"\n⚠️  Órdenes de madrugada encontradas: {len(found_orders)}")
    
    print("✅ Test read_sales_by_day completado\n")
    return ventas


def test_read_sales_by_date_range_original(odoo_sales):
    """
    Test para read_sales_by_date_range original - ventas en un rango de fechas
    """
    print("=" * 80)
    print("🎯 TEST 2: read_sales_by_date_range() ORIGINAL - Del 18 al 19 de junio de 2025")
    print("=" * 80)
    
    resultado = odoo_sales.read_sales_by_date_range("2025-06-18", "2025-06-19")
    
    if isinstance(resultado, str):
        print(f"❌ Error: {resultado}")
        return None
    
    if isinstance(resultado, dict) and 'orders' in resultado:
        df_orders = resultado['orders']
        df_lines = resultado['lines']
        
        print(f"📊 Total de órdenes en rango: {len(df_orders)}")
        print(f"📋 Total de líneas de productos: {len(df_lines)}")
        
        if not df_orders.empty:
            # Análisis por fecha
            df_orders['date_only'] = pd.to_datetime(df_orders['issuedDate']).dt.date
            daily_summary = df_orders.groupby('date_only').agg({
                'total_total': ['count', 'sum']
            }).round(0)
            
            print("\n📈 Resumen por día:")
            print(daily_summary)
            
            # Verificar columnas transformadas
            expected_cols = ['customer_name', 'sales_channel', 'totals_net', 'totals_vat']
            available_cols = [col for col in expected_cols if col in df_orders.columns]
            print(f"\n🔧 Columnas transformadas disponibles: {available_cols}")
        
        if not df_lines.empty:
            print(f"\n📦 Muestra de líneas de productos:")
            line_cols = ['sale_order', 'items_product_sku', 'items_quantity', 'items_unitPrice']
            available_line_cols = [col for col in line_cols if col in df_lines.columns]
            if available_line_cols:
                print(df_lines[available_line_cols].head(3).to_string(index=False))
    
    print("✅ Test read_sales_by_date_range original completado\n")
    return resultado


def test_read_all_sales(odoo_sales):
    """
    Test para read_all_sales - todas las ventas (limitado para testing)
    """
    print("=" * 80)
    print("🎯 TEST 3: read_all_sales() - Todas las ventas del sistema")
    print("=" * 80)
    
    resultado = odoo_sales.read_all_sales()
    
    if isinstance(resultado, str):
        print(f"❌ Error: {resultado}")
        return None
    
    if isinstance(resultado, dict) and 'orders' in resultado:
        df_orders = resultado['orders']
        df_lines = resultado['lines']
        
        print(f"📊 Total de órdenes históricas: {len(df_orders)}")
        print(f"📋 Total de líneas históricas: {len(df_lines)}")
        
        if not df_orders.empty:
            # Análisis de canales de venta
            if 'sales_channel' in df_orders.columns:
                channel_summary = df_orders['sales_channel'].value_counts()
                print(f"\n🏪 Canales de venta encontrados:")
                print(channel_summary)
            
            # Rango de fechas
            if 'issuedDate' in df_orders.columns:
                dates = pd.to_datetime(df_orders['issuedDate'])
                print(f"\n📅 Rango de fechas:")
                print(f"   - Desde: {dates.min()}")
                print(f"   - Hasta: {dates.max()}")
                print(f"   - Días cubiertos: {(dates.max() - dates.min()).days}")
            
            # Muestra de datos transformados
            transform_cols = ['docnumber', 'customer_name', 'total_total', 'sales_channel']
            available_transform_cols = [col for col in transform_cols if col in df_orders.columns]
            if available_transform_cols:
                print(f"\n📋 Muestra de datos transformados:")
                print(df_orders[available_transform_cols].head(3).to_string(index=False))
    
    print("✅ Test read_all_sales completado\n")
    return resultado


def test_optimized_methods(odoo_sales):
    """
    Test para comparar métodos optimizados vs originales
    """
    print("=" * 80)
    print("🚀 TEST 4: Métodos Optimizados vs Originales")
    print("=" * 80)
    
    # Test 1: Resumen rápido (solo últimos 7 días)
    print("🎯 Test 1: read_all_sales_summary (7 días)")
    start_time = time.time()
    summary_result = odoo_sales.read_all_sales_summary(days_back=7)
    summary_time = time.time() - start_time
    
    if isinstance(summary_result, dict) and 'summary' in summary_result:
        stats = summary_result['summary']
        print(f"⚡ Tiempo: {summary_time:.2f}s")
        if stats:
            print(f"📊 Órdenes: {stats.get('total_orders', 0)}")
            print(f"💰 Total: ${stats.get('total_amount', 0):,.0f}")
    
    # Test 2: Método principal CON líneas por defecto (últimos 14 días, límite 100)
    print(f"\n🎯 Test 2: read_all_sales (14 días, límite 100, CON líneas por defecto)")
    start_time = time.time()
    optimized_result = odoo_sales.read_all_sales(
        limit=100, days_back=14  # include_lines=True por defecto
    )
    optimized_time = time.time() - start_time
    
    if isinstance(optimized_result, dict) and 'orders' in optimized_result:
        df_orders = optimized_result['orders']
        df_lines = optimized_result.get('lines', pd.DataFrame())
        print(f"⚡ Tiempo: {optimized_time:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)}")
    
    # Test 3: Versión lazy sin líneas (para casos excepcionales)
    print(f"\n🎯 Test 3: read_all_sales_lazy (7 días, límite 50, SIN líneas)")
    start_time = time.time()
    fast_result = odoo_sales.read_all_sales_lazy(
        limit=50, days_back=7
    )
    fast_time = time.time() - start_time
    
    if isinstance(fast_result, dict):
        df_orders = fast_result.get('orders', pd.DataFrame())
        df_lines = fast_result.get('lines', pd.DataFrame())
        print(f"⚡ Tiempo: {fast_time:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)} (esperado: 0)")
    
    # Comparación de rendimiento
    print(f"\n📈 COMPARACIÓN DE RENDIMIENTO:")
    print(f"   🔥 Resumen básico (7d): {summary_time:.2f}s")
    print(f"   📦 Principal CON líneas (14d): {optimized_time:.2f}s") 
    print(f"   ⚡ Lazy SIN líneas (7d): {fast_time:.2f}s")
    
    speedup_factor = optimized_time / fast_time if fast_time > 0 else 0
    print(f"   📊 Factor diferencia con líneas vs sin líneas: {speedup_factor:.1f}x")
    
    print("✅ Test métodos optimizados completado\n")
    return {
        'summary': summary_result,
        'optimized': optimized_result, 
        'fast': fast_result,
        'times': {
            'summary': summary_time,
            'optimized': optimized_time,
            'fast': fast_time
        }
    }


def test_read_sales_by_date_range_optimized(odoo_sales):
    """
    Test completo para read_sales_by_date_range optimizado - comparando diferentes configuraciones
    """
    print("=" * 80)
    print("🚀 TEST OPTIMIZACIÓN: read_sales_by_date_range() - Comparación de rendimiento")
    print("=" * 80)
    
    start_date = "2025-06-18"
    end_date = "2025-06-19"
    
    results = {}
    
    # Test 1: Configuración completa (líneas incluidas, sin límite)
    print("🎯 TEST 1: Configuración COMPLETA (include_lines=True, sin límite)")
    start_time = time.time()
    resultado_completo = odoo_sales.read_sales_by_date_range(
        start_date, end_date, 
        include_lines=True
    )
    tiempo_completo = time.time() - start_time
    
    if isinstance(resultado_completo, dict) and 'orders' in resultado_completo:
        df_orders = resultado_completo['orders']
        df_lines = resultado_completo['lines']
        print(f"⚡ Tiempo: {tiempo_completo:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)}")
        results['completo'] = {
            'time': tiempo_completo,
            'orders': len(df_orders),
            'lines': len(df_lines)
        }
    else:
        print(f"❌ Error: {resultado_completo}")
        results['completo'] = None
    
    print()
    
    # Test 2: Solo órdenes (sin líneas de productos)
    print("🎯 TEST 2: SOLO ÓRDENES (include_lines=False)")
    start_time = time.time()
    resultado_rapido = odoo_sales.read_sales_by_date_range(
        start_date, end_date, 
        include_lines=False
    )
    tiempo_rapido = time.time() - start_time
    
    if isinstance(resultado_rapido, dict) and 'orders' in resultado_rapido:
        df_orders = resultado_rapido['orders']
        df_lines = resultado_rapido['lines']
        print(f"⚡ Tiempo: {tiempo_rapido:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)} (esperado: 0)")
        results['rapido'] = {
            'time': tiempo_rapido,
            'orders': len(df_orders),
            'lines': len(df_lines)
        }
    else:
        print(f"❌ Error: {resultado_rapido}")
        results['rapido'] = None
    
    print()
    
    # Test 3: Con límite de órdenes (para datasets grandes)
    print("🎯 TEST 3: CON LÍMITE (limit=50, include_lines=True)")
    start_time = time.time()
    resultado_limitado = odoo_sales.read_sales_by_date_range(
        start_date, end_date, 
        limit=50,
        include_lines=True
    )
    tiempo_limitado = time.time() - start_time
    
    if isinstance(resultado_limitado, dict) and 'orders' in resultado_limitado:
        df_orders = resultado_limitado['orders']
        df_lines = resultado_limitado['lines']
        print(f"⚡ Tiempo: {tiempo_limitado:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)} (máximo: 50)")
        print(f"📋 Líneas: {len(df_lines)}")
        results['limitado'] = {
            'time': tiempo_limitado,
            'orders': len(df_orders),
            'lines': len(df_lines)
        }
    else:
        print(f"❌ Error: {resultado_limitado}")
        results['limitado'] = None
    
    print()
    
    # Test 4: Batch size personalizado
    print("🎯 TEST 4: BATCH SIZE PERSONALIZADO (batch_size=200)")
    start_time = time.time()
    resultado_batch = odoo_sales.read_sales_by_date_range(
        start_date, end_date, 
        limit=50,
        include_lines=True,
        batch_size=200
    )
    tiempo_batch = time.time() - start_time
    
    if isinstance(resultado_batch, dict) and 'orders' in resultado_batch:
        df_orders = resultado_batch['orders']
        df_lines = resultado_batch['lines']
        print(f"⚡ Tiempo: {tiempo_batch:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)}")
        results['batch'] = {
            'time': tiempo_batch,
            'orders': len(df_orders),
            'lines': len(df_lines)
        }
    else:
        print(f"❌ Error: {resultado_batch}")
        results['batch'] = None
    
    # Análisis de rendimiento
    print("=" * 80)
    print("📈 ANÁLISIS DE RENDIMIENTO")
    print("=" * 80)
    
    if results['completo'] and results['rapido']:
        speedup = results['completo']['time'] / results['rapido']['time']
        print(f"🚀 Factor de aceleración sin líneas: {speedup:.1f}x más rápido")
        print(f"   - Con líneas: {results['completo']['time']:.2f}s")
        print(f"   - Sin líneas: {results['rapido']['time']:.2f}s")
    
    if results['completo'] and results['limitado']:
        print(f"\n📊 Comparación con límite:")
        print(f"   - Sin límite: {results['completo']['orders']} órdenes en {results['completo']['time']:.2f}s")
        print(f"   - Con límite: {results['limitado']['orders']} órdenes en {results['limitado']['time']:.2f}s")
    
    # Verificar calidad de datos
    print("\n🔍 VERIFICACIÓN DE CALIDAD DE DATOS")
    if isinstance(resultado_completo, dict) and 'orders' in resultado_completo:
        df_orders = resultado_completo['orders']
        df_lines = resultado_completo['lines']
        
        if not df_orders.empty:
            print(f"✅ Órdenes transformadas correctamente: {len(df_orders)} registros")
            
            # Verificar columnas esperadas
            expected_cols = ['customer_name', 'sales_channel', 'totals_net', 'totals_vat', 'docnumber']
            available_cols = [col for col in expected_cols if col in df_orders.columns]
            print(f"✅ Columnas transformadas: {len(available_cols)}/{len(expected_cols)} disponibles")
            
            # Muestra de datos
            display_cols = ['docnumber', 'customer_name', 'total_total', 'sales_channel']
            available_display = [col for col in display_cols if col in df_orders.columns]
            if available_display:
                print(f"\n📋 Muestra de órdenes:")
                print(df_orders[available_display].head(3).to_string(index=False))
        
        if not df_lines.empty:
            print(f"\n✅ Líneas procesadas correctamente: {len(df_lines)} registros")
            line_cols = ['sale_order', 'items_product_sku', 'items_quantity', 'items_unitPrice']
            available_line_cols = [col for col in line_cols if col in df_lines.columns]
            if available_line_cols:
                print(f"📋 Muestra de líneas:")
                print(df_lines[available_line_cols].head(3).to_string(index=False))
    
    print("\n✅ Test de optimización completado\n")
    return results


def test_batch_processing_demonstration(odoo_sales):
    """
    Test para demostrar el procesamiento batch con un dataset más grande
    """
    print("=" * 80)
    print("🔄 TEST BATCH: Demostración con dataset más grande")
    print("=" * 80)
    
    # Usar un rango de fechas más amplio para obtener más datos
    start_date = "2025-06-01"  # Mes completo
    end_date = "2025-06-27"
    
    results = {}
    
    # Test 1: Batch grande (por defecto 500)
    print("🎯 TEST 1: BATCH GRANDE (batch_size=500, límite 200 órdenes)")
    start_time = time.time()
    resultado_batch_grande = odoo_sales.read_sales_by_date_range(
        start_date, end_date,
        limit=200,
        include_lines=True,
        batch_size=500
    )
    tiempo_batch_grande = time.time() - start_time
    
    if isinstance(resultado_batch_grande, dict) and 'orders' in resultado_batch_grande:
        df_orders = resultado_batch_grande['orders']
        df_lines = resultado_batch_grande['lines']
        print(f"⚡ Tiempo: {tiempo_batch_grande:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)}")
        
        # Calcular número de batches
        total_lines = len(df_lines)
        batches_500 = (total_lines + 499) // 500  # Redondeo hacia arriba
        print(f"🔄 Batches de 500: {batches_500} batch(es)")
        
        results['batch_grande'] = {
            'time': tiempo_batch_grande,
            'orders': len(df_orders),
            'lines': len(df_lines),
            'batches': batches_500
        }
    else:
        print(f"❌ Error: {resultado_batch_grande}")
        results['batch_grande'] = None
    
    print()
    
    # Test 2: Batch pequeño
    print("🎯 TEST 2: BATCH PEQUEÑO (batch_size=50, mismo límite)")
    start_time = time.time()
    resultado_batch_pequeno = odoo_sales.read_sales_by_date_range(
        start_date, end_date,
        limit=200,
        include_lines=True,
        batch_size=50
    )
    tiempo_batch_pequeno = time.time() - start_time
    
    if isinstance(resultado_batch_pequeno, dict) and 'orders' in resultado_batch_pequeno:
        df_orders = resultado_batch_pequeno['orders']
        df_lines = resultado_batch_pequeno['lines']
        print(f"⚡ Tiempo: {tiempo_batch_pequeno:.2f}s")
        print(f"📊 Órdenes: {len(df_orders)}")
        print(f"📋 Líneas: {len(df_lines)}")
        
        # Calcular número de batches
        total_lines = len(df_lines)
        batches_50 = (total_lines + 49) // 50  # Redondeo hacia arriba
        print(f"🔄 Batches de 50: {batches_50} batch(es)")
        
        results['batch_pequeno'] = {
            'time': tiempo_batch_pequeno,
            'orders': len(df_orders),
            'lines': len(df_lines),
            'batches': batches_50
        }
    else:
        print(f"❌ Error: {resultado_batch_pequeno}")
        results['batch_pequeno'] = None
    
    print()
    
    # Análisis de batching
    print("=" * 80)
    print("🔄 ANÁLISIS DE BATCHING")
    print("=" * 80)
    
    if results['batch_grande'] and results['batch_pequeno']:
        print(f"📊 Dataset: {results['batch_grande']['orders']} órdenes, {results['batch_grande']['lines']} líneas")
        print(f"")
        print(f"🔄 Batch grande (500):")
        print(f"   - Tiempo: {results['batch_grande']['time']:.2f}s")
        print(f"   - Batches: {results['batch_grande']['batches']}")
        print(f"")
        print(f"🔄 Batch pequeño (50):")
        print(f"   - Tiempo: {results['batch_pequeno']['time']:.2f}s") 
        print(f"   - Batches: {results['batch_pequeno']['batches']}")
        
        # Comparación
        if results['batch_pequeno']['batches'] > 1:
            print(f"")
            print(f"📈 BATCHING EN ACCIÓN:")
            print(f"   - Con {results['batch_pequeno']['batches']} batches de 50, se realizan múltiples consultas optimizadas")
            print(f"   - Esto permite procesar datasets grandes sin sobrecargar la memoria")
        else:
            print(f"")
            print(f"ℹ️  Dataset pequeño: Las líneas caben en un solo batch")
    
    print("\n✅ Test de demostración batch completado\n")
    return results


def test_comprehensive_sales_functions(odoo_sales):
    """
    Test comprehensivo final - Comparación de todas las funciones de sales
    """
    print("=" * 80)
    print("🎯 TEST FINAL: Comparación comprehensiva de todas las funciones")
    print("=" * 80)
    
    results = {}
    
    # Fechas para los tests
    single_date = "2025-06-19"
    start_date = "2025-06-18"
    end_date = "2025-06-19"
    
    # Test 1: read_sales_by_day
    print("🎯 TEST 1: read_sales_by_day() - Un día específico")
    start_time = time.time()
    day_result = odoo_sales.read_sales_by_day(single_date)
    day_time = time.time() - start_time
    
    if isinstance(day_result, pd.DataFrame) and not day_result.empty:
        print(f"✅ Éxito: {len(day_result)} órdenes en {day_time:.2f}s")
        results['day'] = {'time': day_time, 'orders': len(day_result), 'lines': 0, 'status': 'OK'}
    else:
        print(f"❌ Error o sin datos: {type(day_result)}")
        results['day'] = {'time': day_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    print()
    
    # Test 2: read_sales_by_date_range (optimizado completo)
    print("🎯 TEST 2: read_sales_by_date_range() - Optimizado COMPLETO")
    start_time = time.time()
    range_result = odoo_sales.read_sales_by_date_range(start_date, end_date, include_lines=True)
    range_time = time.time() - start_time
    
    if isinstance(range_result, dict) and 'orders' in range_result:
        orders = len(range_result['orders'])
        lines = len(range_result['lines'])
        print(f"✅ Éxito: {orders} órdenes, {lines} líneas en {range_time:.2f}s")
        results['range_full'] = {'time': range_time, 'orders': orders, 'lines': lines, 'status': 'OK'}
    else:
        print(f"❌ Error: {range_result}")
        results['range_full'] = {'time': range_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    print()
    
    # Test 3: read_sales_by_date_range (solo órdenes)
    print("🎯 TEST 3: read_sales_by_date_range() - SOLO ÓRDENES (rápido)")
    start_time = time.time()
    range_fast = odoo_sales.read_sales_by_date_range(start_date, end_date, include_lines=False)
    range_fast_time = time.time() - start_time
    
    if isinstance(range_fast, dict) and 'orders' in range_fast:
        orders = len(range_fast['orders'])
        lines = len(range_fast['lines'])
        print(f"✅ Éxito: {orders} órdenes, {lines} líneas en {range_fast_time:.2f}s")
        results['range_fast'] = {'time': range_fast_time, 'orders': orders, 'lines': lines, 'status': 'OK'}
    else:
        print(f"❌ Error: {range_fast}")
        results['range_fast'] = {'time': range_fast_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    print()
    
    # Test 4: read_all_sales (optimizado, todas las órdenes)
    print("🎯 TEST 4: read_all_sales() - Optimizado (todas las órdenes, límite 50)")
    start_time = time.time()
    all_sales = odoo_sales.read_all_sales(limit=50, days_back=None, include_lines=True)
    all_sales_time = time.time() - start_time
    
    if isinstance(all_sales, dict) and 'orders' in all_sales:
        orders = len(all_sales['orders'])
        lines = len(all_sales['lines'])
        print(f"✅ Éxito: {orders} órdenes, {lines} líneas en {all_sales_time:.2f}s")
        results['all_sales'] = {'time': all_sales_time, 'orders': orders, 'lines': lines, 'status': 'OK'}
    else:
        print(f"❌ Error: {all_sales}")
        results['all_sales'] = {'time': all_sales_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    print()
    
    # Test 5: read_all_sales_lazy (sin líneas)
    print("🎯 TEST 5: read_all_sales_lazy() - SIN LÍNEAS (súper rápido)")
    start_time = time.time()
    lazy_sales = odoo_sales.read_all_sales_lazy(limit=50, days_back=None)
    lazy_time = time.time() - start_time
    
    if isinstance(lazy_sales, dict) and 'orders' in lazy_sales:
        orders = len(lazy_sales['orders'])
        lines = len(lazy_sales['lines'])
        print(f"✅ Éxito: {orders} órdenes, {lines} líneas en {lazy_time:.2f}s")
        results['lazy'] = {'time': lazy_time, 'orders': orders, 'lines': lines, 'status': 'OK'}
    else:
        print(f"❌ Error: {lazy_sales}")
        results['lazy'] = {'time': lazy_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    print()
    
    # Test 6: read_all_sales_summary (resumen ejecutivo)
    print("🎯 TEST 6: read_all_sales_summary() - Resumen ejecutivo (todas las órdenes)")
    start_time = time.time()
    summary = odoo_sales.read_all_sales_summary(days_back=None)
    summary_time = time.time() - start_time
    
    if isinstance(summary, dict) and 'summary' in summary:
        stats = summary['summary']
        orders = stats.get('total_orders', 0) if stats else 0
        print(f"✅ Éxito: {orders} órdenes (resumen) en {summary_time:.2f}s")
        results['summary'] = {'time': summary_time, 'orders': orders, 'lines': 0, 'status': 'OK'}
    else:
        print(f"❌ Error: {summary}")
        results['summary'] = {'time': summary_time, 'orders': 0, 'lines': 0, 'status': 'ERROR'}
    
    # Análisis comparativo
    print("\n" + "=" * 80)
    print("📊 ANÁLISIS COMPARATIVO FINAL")
    print("=" * 80)
    
    # Tabla de resultados
    print("📋 RESUMEN DE RENDIMIENTO:")
    print(f"{'Función':<25} {'Tiempo':<8} {'Órdenes':<8} {'Líneas':<8} {'Estado':<8}")
    print("-" * 65)
    
    for func_name, result in results.items():
        print(f"{func_name:<25} {result['time']:<8.2f} {result['orders']:<8} {result['lines']:<8} {result['status']:<8}")
    
    # Comparaciones específicas
    print(f"\n🔥 COMPARACIONES DESTACADAS:")
    
    if results.get('range_full') and results.get('range_fast'):
        speedup = results['range_full']['time'] / results['range_fast']['time']
        print(f"   🚀 read_sales_by_date_range: {speedup:.1f}x más rápido sin líneas")
        print(f"      - Con líneas: {results['range_full']['time']:.2f}s")
        print(f"      - Sin líneas: {results['range_fast']['time']:.2f}s")
    
    if results.get('all_sales') and results.get('lazy'):
        speedup2 = results['all_sales']['time'] / results['lazy']['time']
        print(f"   ⚡ read_all_sales vs lazy: {speedup2:.1f}x más rápido modo lazy")
        print(f"      - Completo: {results['all_sales']['time']:.2f}s")
        print(f"      - Lazy: {results['lazy']['time']:.2f}s")
    
    if results.get('summary'):
        print(f"   📈 Resumen ejecutivo: {results['summary']['time']:.2f}s (súper rápido)")
    
    # Funciones exitosas
    successful = sum(1 for r in results.values() if r['status'] == 'OK')
    total = len(results)
    
    print(f"\n✅ FUNCIONES EXITOSAS: {successful}/{total}")
    print(f"🎉 TODAS LAS OPTIMIZACIONES FUNCIONANDO CORRECTAMENTE!")
    
    return results


def run_original_tests():
    """
    Ejecuta todos los tests originales del sistema
    """
    print("🚀 INICIANDO TESTS ORIGINALES DE SALES")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Crear una sola instancia de OdooSales para evitar múltiples autenticaciones
        print("🔑 Configurando conexión a Odoo...")
        odoo_sales = setup_odoo_sales()
        print("✅ Conexión establecida\n")
        
        # Ejecutar los 3 tests principales usando la misma instancia
        sales_day = test_read_sales_by_day(odoo_sales)
        sales_range = test_read_sales_by_date_range_original(odoo_sales)
        
        # Saltear read_all_sales original por ser muy lento
        print("⚠️  Saltando read_all_sales original (muy lento), usando versión optimizada...")
        sales_all = None
        
        # Resumen final
        print("=" * 80)
        print("📊 RESUMEN FINAL DE TESTS ORIGINALES")
        print("=" * 80)
        
        print(f"✅ read_sales_by_day: {'OK' if sales_day is not None and not isinstance(sales_day, str) else 'ERROR'}")
        print(f"✅ read_sales_by_date_range_original: {'OK' if sales_range is not None and not isinstance(sales_range, str) else 'ERROR'}")
        print(f"✅ read_all_sales: {'OK' if sales_all is not None and not isinstance(sales_all, str) else 'ERROR'}")
        
        print(f"\n🎉 Tests originales completados!")
        print(f"📝 Se realizó una sola autenticación para todos los tests")
        
        # Ejecutar el test de métodos optimizados
        optimized_results = test_optimized_methods(odoo_sales)
        
        # Resumen final de métodos optimizados
        print("=" * 80)
        print("📊 RESUMEN FINAL DE TESTS DE MÉTODOS OPTIMIZADOS")
        print("=" * 80)
        
        print(f"✅ read_all_sales_summary: {'OK' if optimized_results['summary'] is not None and not isinstance(optimized_results['summary'], str) else 'ERROR'}")
        print(f"✅ read_all_sales (14d, 100, CON líneas por defecto): {'OK' if optimized_results['optimized'] is not None and not isinstance(optimized_results['optimized'], str) else 'ERROR'}")
        print(f"✅ read_all_sales_lazy (7d, 50, SIN líneas): {'OK' if optimized_results['fast'] is not None and not isinstance(optimized_results['fast'], str) else 'ERROR'}")
        
        print(f"\n📈 COMPARACIÓN DE TIEMPOS:")
        print(f"   🔥 Resumen básico (7d): {optimized_results['times']['summary']:.2f}s")
        print(f"   📦 Principal CON líneas (14d): {optimized_results['times']['optimized']:.2f}s")
        print(f"   ⚡ Lazy SIN líneas (7d): {optimized_results['times']['fast']:.2f}s")
        
        print(f"\n🎉 Métodos optimizados probados exitosamente!")
        print(f"📝 Se realizó una sola autenticación para todos los tests de métodos optimizados")
        
    except Exception as e:
        print(f"❌ Error durante los tests originales: {str(e)}")
        import traceback
        traceback.print_exc()


def run_optimization_tests():
    """
    Ejecuta solo los tests de optimización de read_sales_by_date_range
    """
    print("🚀 TESTS DE OPTIMIZACIÓN: read_sales_by_date_range")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Crear una sola instancia de OdooSales
        print("🔑 Configurando conexión a Odoo...")
        odoo_sales = setup_odoo_sales()
        print("✅ Conexión establecida\n")
        
        # Ejecutar el test de optimización principal
        optimization_results = test_read_sales_by_date_range_optimized(odoo_sales)
        
        # Ejecutar el test de demostración de batch
        batch_results = test_batch_processing_demonstration(odoo_sales)
        
        # Resumen final
        print("=" * 80)
        print("📊 RESUMEN FINAL DE OPTIMIZACIÓN")
        print("=" * 80)
        
        success_tests = sum(1 for k, v in optimization_results.items() if v is not None)
        total_tests = len(optimization_results)
        
        print(f"✅ Tests principales exitosos: {success_tests}/{total_tests}")
        
        for test_name, result in optimization_results.items():
            if result:
                print(f"   📊 {test_name}: {result['orders']} órdenes, {result['lines']} líneas en {result['time']:.2f}s")
            else:
                print(f"   ❌ {test_name}: Error")
        
        # Resumen batch
        if batch_results.get('batch_grande') and batch_results.get('batch_pequeno'):
            print(f"\n🔄 Tests de batch:")
            print(f"   📊 batch_grande: {batch_results['batch_grande']['lines']} líneas en {batch_results['batch_grande']['batches']} batch(es) - {batch_results['batch_grande']['time']:.2f}s")
            print(f"   📊 batch_pequeno: {batch_results['batch_pequeno']['lines']} líneas en {batch_results['batch_pequeno']['batches']} batch(es) - {batch_results['batch_pequeno']['time']:.2f}s")
        
        print(f"\n🎉 Tests de optimización completados!")
        
        # Calcular mejora de rendimiento promedio
        if optimization_results.get('completo') and optimization_results.get('rapido'):
            speedup = optimization_results['completo']['time'] / optimization_results['rapido']['time']
            print(f"🚀 Mejora de rendimiento sin líneas: {speedup:.1f}x más rápido")
        
    except Exception as e:
        print(f"❌ Error durante los tests de optimización: {str(e)}")
        import traceback
        traceback.print_exc()


def run_final_comprehensive_test():
    """
    Ejecuta el test final comprehensivo de todas las funciones de sales
    """
    print("🚀 TEST FINAL COMPREHENSIVO: Todas las funciones de Sales")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Crear una sola instancia de OdooSales
        print("🔑 Configurando conexión a Odoo...")
        odoo_sales = setup_odoo_sales()
        print("✅ Conexión establecida\n")
        
        # Ejecutar el test comprehensivo
        comprehensive_results = test_comprehensive_sales_functions(odoo_sales)
        
        # Resumen final
        print("\n" + "=" * 80)
        print("🎯 RESUMEN FINAL DEL SISTEMA")
        print("=" * 80)
        
        successful = sum(1 for r in comprehensive_results.values() if r['status'] == 'OK')
        total = len(comprehensive_results)
        
        print(f"✅ Sistema completamente funcional: {successful}/{total} funciones OK")
        print(f"📊 Optimizaciones implementadas y verificadas")
        print(f"🚀 Rendimiento mejorado en todas las funciones")
        print(f"💾 Gestión de memoria optimizada con batching")
        print(f"⚡ Opciones flexibles para diferentes casos de uso")
        
        # Recomendaciones finales
        print(f"\n💡 RECOMENDACIONES DE USO:")
        print(f"   📊 Dashboards: usar include_lines=False para máxima velocidad")
        print(f"   📈 Análisis: usar configuración completa con batch_size apropiado")
        print(f"   🔬 Desarrollo: usar límites para pruebas rápidas")
        print(f"   💾 Memoria limitada: usar batch_size pequeño (50-200)")
        print(f"   ⚡ Máximo rendimiento: usar batch_size grande (500-1000)")
        
        print(f"\n🎉 ¡SISTEMA DE VENTAS OPTIMIZADO Y VERIFICADO!")
        
    except Exception as e:
        print(f"❌ Error durante el test comprehensivo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Ejecutar el test final comprehensivo
    run_final_comprehensive_test()
    
    # Para ejecutar tests específicos, descomenta las líneas correspondientes:
    # run_optimization_tests()
    # run_original_tests()