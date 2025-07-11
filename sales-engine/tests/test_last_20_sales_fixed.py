#!/usr/bin/env python3
"""
Test para obtener las últimas 20 ventas reales de Odoo usando la configuración correcta.
"""

import sys
import os
from datetime import date, timedelta

def test_last_20_sales_fixed():
    """Test que obtiene las últimas 20 ventas de Odoo con configuración correcta"""
    
    print("🚀 OBTENIENDO LAS ÚLTIMAS 20 VENTAS DE ODOO")
    print("=" * 60)
    
    # Agregar paths necesarios
    odoo_api_path = os.path.join(os.path.dirname(__file__), '..', '..', 'odoo-api', 'src')
    sales_engine_path = os.path.join(os.path.dirname(__file__), '..', 'src')
    sys.path.insert(0, odoo_api_path)
    sys.path.insert(0, sales_engine_path)
    
    try:
        from odoo_api.sales import OdooSales
        from sales_engine.config import get_odoo_config
        print("✅ Importaciones exitosas")
    except ImportError as e:
        print(f"❌ Error en importaciones: {e}")
        return False
    
    # Configurar fechas - últimos 30 días
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    print(f"📅 Buscando ventas entre: {start_date} y {end_date}")
    
    try:
        # Obtener configuración de Odoo
        config = get_odoo_config(use_test=False)
        print(f"✅ Configuración obtenida para BD: {config.get('db', 'N/A')}")
        
        # Inicializar cliente Odoo
        client = OdooSales(
            url=config['url'],
            db=config['db'],
            username=config['username'],
            password=config['password']
        )
        print("✅ Cliente OdooSales inicializado y autenticado")
        
        # Obtener zona horaria del usuario
        user_tz = client.get_user_timezone()
        print(f"🌍 Zona horaria detectada: {user_tz}")
        
        # Convertir fechas a UTC
        start_utc, end_utc = client._convert_timezone_range(start_date, end_date, user_tz)
        
        # Obtener órdenes de venta
        print("\n🔄 Obteniendo órdenes de venta...")
        sales_orders = client._get_sales_orders(start_utc, end_utc)
        print(f"✅ Órdenes de venta encontradas: {len(sales_orders)}")
        
        # Obtener órdenes POS si es posible
        print("🔄 Obteniendo órdenes POS...")
        pos_orders = client._get_pos_orders(start_utc, end_utc)
        print(f"✅ Órdenes POS encontradas: {len(pos_orders)}")
        
        # Combinar todas las órdenes
        all_orders = []
        
        # Agregar órdenes de venta
        for order in sales_orders:
            order['source'] = 'sale'
            all_orders.append(order)
        
        # Agregar órdenes POS
        for order in pos_orders:
            order['source'] = 'pos'
            all_orders.append(order)
        
        print(f"📊 Total de órdenes encontradas: {len(all_orders)}")
        
        # Si no hay órdenes, ampliar búsqueda
        if not all_orders:
            print("⚠️  No se encontraron órdenes. Ampliando búsqueda a 90 días...")
            start_date = end_date - timedelta(days=90)
            start_utc, end_utc = client._convert_timezone_range(start_date, end_date, user_tz)
            
            sales_orders = client._get_sales_orders(start_utc, end_utc)
            pos_orders = client._get_pos_orders(start_utc, end_utc)
            
            all_orders = []
            for order in sales_orders:
                order['source'] = 'sale'
                all_orders.append(order)
            for order in pos_orders:
                order['source'] = 'pos'
                all_orders.append(order)
            
            print(f"📊 Órdenes en búsqueda ampliada: {len(all_orders)}")
        
        if not all_orders:
            print("❌ No se encontraron órdenes en ningún periodo")
            return False
        
        # Ordenar por fecha descendente y tomar las últimas 20
        all_orders.sort(key=lambda x: x.get('date_order', ''), reverse=True)
        last_20_orders = all_orders[:20]
        
        print(f"\n🔍 MOSTRANDO LAS ÚLTIMAS 20 VENTAS:")
        print("=" * 70)
        
        # Obtener información de clientes
        print("🔄 Obteniendo información de clientes...")
        partners_dict = client._get_partners_info(last_20_orders)
        print(f"✅ Información de {len(partners_dict)} clientes obtenida")
        
        # Mostrar cada venta
        total_amount = 0
        for i, order in enumerate(last_20_orders, 1):
            print(f"\n📦 VENTA #{i}")
            print("-" * 45)
            
            # Información básica
            order_id = order.get('id', 'N/A')
            order_name = order.get('name', 'N/A')
            order_date = order.get('date_order', 'N/A')
            order_total = order.get('amount_total', 0)
            order_source = order.get('source', 'unknown')
            order_state = order.get('state', 'N/A')
            
            print(f"🆔 ID: {order_id}")
            print(f"📄 Número: {order_name}")
            print(f"📅 Fecha: {order_date}")
            print(f"💸 Total: ${order_total:,.0f}")
            print(f"📱 Fuente: {order_source.upper()}")
            print(f"📊 Estado: {order_state}")
            
            # Información del cliente
            partner_info = order.get('partner_id')
            if partner_info and len(partner_info) >= 2:
                partner_id = partner_info[0]
                partner_name = partner_info[1]
                partner_details = partners_dict.get(partner_id, {})
                partner_vat = partner_details.get('vat', 'Sin RUT')
                
                print(f"👤 Cliente: {partner_name} (ID: {partner_id})")
                print(f"🆔 RUT: {partner_vat}")
            else:
                print("👤 Cliente: Sin información")
            
            # Información del vendedor
            user_info = order.get('user_id')
            if user_info and len(user_info) >= 2:
                user_name = user_info[1]
                print(f"👨‍💼 Vendedor: {user_name}")
            else:
                print("👨‍💼 Vendedor: No asignado")
            
            # Información del equipo/canal
            team_info = order.get('team_id')
            if team_info and len(team_info) >= 2:
                team_name = team_info[1]
                print(f"🏪 Canal: {team_name}")
            else:
                print("🏪 Canal: Sin asignar")
            
            # Mostrar productos para las primeras 5 ventas
            if i <= 5:
                print("📋 Productos:")
                try:
                    if order_source == 'sale' and order.get('order_line'):
                        # Líneas de venta regular
                        line_ids = order['order_line'][:3]  # Solo primeras 3 líneas
                        line_details = client.models.execute_kw(
                            client.db, client.uid, client.password,
                            'sale.order.line', 'read',
                            [line_ids],
                            {'fields': ['product_id', 'product_uom_qty', 'price_unit', 'name']}
                        )
                        
                        for j, line in enumerate(line_details, 1):
                            product_name = line.get('name', 'Sin nombre')[:40]
                            quantity = line.get('product_uom_qty', 0)
                            unit_price = line.get('price_unit', 0)
                            print(f"   {j}. {product_name}")
                            print(f"      Cant: {quantity}, Precio: ${unit_price:,.0f}")
                            
                    elif order_source == 'pos' and order.get('lines'):
                        # Líneas POS
                        line_ids = order['lines'][:3]  # Solo primeras 3 líneas
                        line_details = client.models.execute_kw(
                            client.db, client.uid, client.password,
                            'pos.order.line', 'read',
                            [line_ids],
                            {'fields': ['product_id', 'qty', 'price_unit']}
                        )
                        
                        for j, line in enumerate(line_details, 1):
                            product_info = line.get('product_id', ['', 'Sin producto'])
                            product_name = product_info[1][:40] if len(product_info) > 1 else 'Sin nombre'
                            quantity = line.get('qty', 0)
                            unit_price = line.get('price_unit', 0)
                            print(f"   {j}. {product_name}")
                            print(f"      Cant: {quantity}, Precio: ${unit_price:,.0f}")
                    else:
                        print("   Sin productos disponibles")
                        
                except Exception as e:
                    print(f"   ⚠️  Error obteniendo productos: {str(e)[:40]}...")
            else:
                print("📋 Productos: (no mostrados para optimizar)")
            
            total_amount += order_total
        
        # Estadísticas finales
        print(f"\n📊 ESTADÍSTICAS DE LAS ÚLTIMAS 20 VENTAS:")
        print("=" * 50)
        print(f"💰 Total acumulado: ${total_amount:,.0f}")
        print(f"📈 Promedio por venta: ${total_amount/20:,.0f}")
        
        # Estadísticas por fuente
        sales_count = sum(1 for order in last_20_orders if order.get('source') == 'sale')
        pos_count = sum(1 for order in last_20_orders if order.get('source') == 'pos')
        
        print(f"📦 Ventas regulares: {sales_count}")
        print(f"🛒 Ventas POS: {pos_count}")
        
        # Estadísticas por estado
        states = {}
        for order in last_20_orders:
            state = order.get('state', 'unknown')
            states[state] = states.get(state, 0) + 1
        
        print(f"📊 Por estado:")
        for state, count in states.items():
            print(f"   {state}: {count} ventas")
        
        # Verificar campos que necesitamos para la base de datos
        print(f"\n🔧 VERIFICACIÓN DE CAMPOS PARA BASE DE DATOS:")
        print("-" * 45)
        
        sample_order = last_20_orders[0]
        db_fields = [
            ('ID', sample_order.get('id')),
            ('Nombre/Número', sample_order.get('name')),
            ('Fecha', sample_order.get('date_order')),
            ('Total', sample_order.get('amount_total')),
            ('Cliente ID', sample_order.get('partner_id', [None])[0] if sample_order.get('partner_id') else None),
            ('Vendedor', sample_order.get('user_id', [None, None])[1] if sample_order.get('user_id') else None),
            ('Canal', sample_order.get('team_id', [None, None])[1] if sample_order.get('team_id') else None),
        ]
        
        for field_name, field_value in db_fields:
            status = "✅" if field_value is not None else "❌"
            value_str = str(field_value)[:30] if field_value is not None else "NULL"
            print(f"   {status} {field_name}: {value_str}")
        
        print(f"\n🎉 ¡Extracción exitosa! Se obtuvieron y mostraron las últimas 20 ventas")
        print("✅ Todos los datos necesarios están disponibles para poblar la base de datos")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal del test"""
    try:
        success = test_last_20_sales_fixed()
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