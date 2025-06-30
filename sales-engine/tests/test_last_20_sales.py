#!/usr/bin/env python3
"""
Test para obtener las últimas 20 ventas reales de Odoo y mostrar su estructura.
Verifica que todos los campos se extraigan correctamente.
"""

import sys
import os
from datetime import date, timedelta
import json

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_last_20_sales():
    """Obtiene las últimas 20 ventas de Odoo y las imprime"""
    
    print("🚀 EXTRAYENDO LAS ÚLTIMAS 20 VENTAS DE ODOO")
    print("=" * 60)
    
    try:
        # Importar después de agregar al path
        from sales_engine.sales_integration import SalesDataProvider
        print("✅ Conexión a sales_engine establecida")
    except ImportError as e:
        print(f"❌ Error importando sales_engine: {e}")
        # Intentar import directo de odoo-api
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'odoo-api', 'src'))
            from odoo_api.sales import SalesOdooClient
            print("✅ Conexión directa a odoo-api establecida")
            return test_with_direct_odoo_client()
        except ImportError as e2:
            print(f"❌ Error importando odoo-api: {e2}")
            return False
    
    # Configurar fechas - últimos 30 días para asegurar que tenemos datos
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print(f"📅 Buscando ventas entre: {start_date} y {end_date}")
    
    # Inicializar proveedor de datos
    try:
        provider = SalesDataProvider(use_test=False)  # Usar datos reales
        print("✅ Conexión a Odoo establecida")
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return False
    
    try:
        # Extraer ventas con líneas
        print("\n🔄 Extrayendo datos de Odoo...")
        orders_df, lines_df = provider.read_sales_by_date_range(
            start_date=start_date,
            end_date=end_date,
            include_lines=True,
            batch_size=100  # Limitamos el batch
        )
        
        print(f"✅ Extracción completada:")
        print(f"   📦 Total órdenes encontradas: {len(orders_df)}")
        print(f"   📋 Total líneas encontradas: {len(lines_df)}")
        
        if orders_df.empty:
            print("⚠️  No se encontraron ventas en el periodo. Ampliando búsqueda...")
            # Ampliar a 90 días
            start_date = end_date - timedelta(days=90)
            print(f"📅 Buscando en periodo ampliado: {start_date} y {end_date}")
            
            orders_df, lines_df = provider.read_sales_by_date_range(
                start_date=start_date,
                end_date=end_date,
                include_lines=True,
                batch_size=100
            )
            
            print(f"✅ Búsqueda ampliada completada:")
            print(f"   📦 Total órdenes encontradas: {len(orders_df)}")
            print(f"   📋 Total líneas encontradas: {len(lines_df)}")
        
        if orders_df.empty:
            print("❌ No se encontraron ventas en ningún periodo")
            provider.close()
            return False
        
        # Tomar las últimas 20 órdenes (ordenadas por fecha)
        print(f"\n📊 MOSTRANDO LAS ÚLTIMAS 20 VENTAS:")
        print("=" * 80)
        
        # Ordenar por fecha descendente y tomar las primeras 20
        if 'issuedDate' in orders_df.columns:
            orders_df_sorted = orders_df.sort_values('issuedDate', ascending=False)
        else:
            orders_df_sorted = orders_df.tail(20)  # Si no hay fecha, tomar las últimas
            
        last_20_orders = orders_df_sorted.head(20)
        
        print(f"📋 Columnas disponibles en órdenes ({len(orders_df.columns)}):")
        for i, col in enumerate(orders_df.columns):
            print(f"   {i+1:2d}. {col}")
        
        print(f"\n📋 Columnas disponibles en líneas ({len(lines_df.columns) if not lines_df.empty else 0}):")
        if not lines_df.empty:
            for i, col in enumerate(lines_df.columns):
                print(f"   {i+1:2d}. {col}")
        else:
            print("   ⚠️  No hay líneas de productos")
        
        print(f"\n🔍 DETALLE DE LAS ÚLTIMAS 20 VENTAS:")
        print("-" * 80)
        
        for i, (idx, order) in enumerate(last_20_orders.iterrows(), 1):
            print(f"\n📦 VENTA #{i}")
            print("-" * 40)
            
            # Campos principales
            print(f"🆔 ID: {order.get('salesInvoiceId', 'N/A')}")
            print(f"📄 Documento: {order.get('docnumber', 'N/A')} ({order.get('doctype_name', 'N/A')})")
            print(f"📅 Fecha: {order.get('issuedDate', 'N/A')}")
            print(f"👤 Cliente: {order.get('customer_name', 'N/A')} (ID: {order.get('customer_customerid', 'N/A')})")
            print(f"🆔 RUT: {order.get('customer_vatid', 'N/A')}")
            print(f"👨‍💼 Vendedor: {order.get('salesman_name', 'N/A')}")
            print(f"🏪 Canal: {order.get('sales_channel', 'N/A')}")
            
            # Campos mejorados
            print(f"💳 Término de pago: {order.get('term_name', 'N/A')}")
            print(f"🏭 Almacén: {order.get('warehouse_name', 'N/A')}")
            
            # Montos
            print(f"💰 Neto: ${order.get('totals_net', 0):,.0f}")
            print(f"📊 IVA: ${order.get('totals_vat', 0):,.0f}")
            print(f"💸 Total: ${order.get('total_total', 0):,.0f}")
            
            # Buscar líneas de esta orden
            order_id = order.get('salesInvoiceId')
            if not lines_df.empty and order_id:
                order_lines = lines_df[lines_df['salesInvoiceId'] == order_id]
                
                if not order_lines.empty:
                    print(f"📋 Productos ({len(order_lines)} líneas):")
                    for j, (_, line) in enumerate(order_lines.iterrows(), 1):
                        sku = line.get('items_product_sku', 'N/A')
                        desc = line.get('items_product_description', 'N/A')
                        qty = line.get('items_quantity', 0)
                        price = line.get('items_unitPrice', 0)
                        print(f"   {j}. {sku}: {desc}")
                        print(f"      Cantidad: {qty}, Precio: ${price:,.0f}")
                else:
                    print("📋 Sin líneas de productos encontradas")
            else:
                print("📋 Sin información de productos")
        
        # Estadísticas finales
        print(f"\n📊 ESTADÍSTICAS GENERALES:")
        print("=" * 50)
        
        total_sales = last_20_orders['total_total'].sum() if 'total_total' in last_20_orders.columns else 0
        avg_sale = last_20_orders['total_total'].mean() if 'total_total' in last_20_orders.columns else 0
        
        print(f"💰 Total ventas (20 últimas): ${total_sales:,.0f}")
        print(f"📈 Promedio por venta: ${avg_sale:,.0f}")
        
        if not lines_df.empty:
            # Obtener líneas de las últimas 20 órdenes
            last_20_order_ids = last_20_orders['salesInvoiceId'].tolist()
            last_20_lines = lines_df[lines_df['salesInvoiceId'].isin(last_20_order_ids)]
            print(f"📦 Total productos vendidos: {len(last_20_lines)}")
            
            if 'items_quantity' in last_20_lines.columns:
                total_qty = last_20_lines['items_quantity'].sum()
                print(f"📊 Cantidad total de items: {total_qty}")
        
        # Verificar campos mejorados
        print(f"\n🔧 VERIFICACIÓN DE CAMPOS MEJORADOS:")
        print("-" * 40)
        
        improved_fields = ['doctype_name', 'term_name', 'warehouse_name']
        for field in improved_fields:
            if field in last_20_orders.columns:
                filled_count = last_20_orders[field].notna().sum()
                percentage = (filled_count / len(last_20_orders)) * 100
                status = "✅" if percentage >= 90 else "⚠️" if percentage >= 50 else "❌"
                print(f"   {status} {field}: {percentage:.1f}% completo ({filled_count}/20)")
                
                # Mostrar valores únicos
                unique_values = last_20_orders[field].dropna().unique()[:5]
                if len(unique_values) > 0:
                    values_str = ", ".join(str(v)[:30] for v in unique_values)
                    print(f"      📝 Valores: {values_str}")
            else:
                print(f"   ❌ {field}: Campo no encontrado")
        
        provider.close()
        print(f"\n🎉 ¡Extracción exitosa! Se mostraron las últimas 20 ventas")
        return True
        
    except Exception as e:
        print(f"❌ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()
        provider.close()
        return False

def test_with_direct_odoo_client():
    """Test alternativo usando directamente el cliente de Odoo"""
    print("\n🔄 Intentando conexión directa con odoo-api...")
    
    try:
        from odoo_api.sales import SalesOdooClient
        
        # Inicializar cliente
        client = SalesOdooClient()
        print("✅ Cliente Odoo inicializado")
        
        # Obtener las últimas ventas
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        print(f"📅 Buscando ventas entre: {start_date} y {end_date}")
        
        orders, lines = client.get_sales_by_date_range(
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"✅ Datos obtenidos:")
        print(f"   📦 Órdenes: {len(orders) if orders else 0}")
        print(f"   📋 Líneas: {len(lines) if lines else 0}")
        
        if orders and len(orders) > 0:
            print(f"\n📊 PRIMERAS 5 ÓRDENES (muestra):")
            for i, order in enumerate(orders[:5], 1):
                print(f"\n   📦 Orden #{i}:")
                for key, value in order.items():
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"      {key}: {value}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error con cliente directo: {e}")
        return False

def main():
    """Función principal del test"""
    try:
        success = test_last_20_sales()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⏹️  Test interrumpido por el usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 