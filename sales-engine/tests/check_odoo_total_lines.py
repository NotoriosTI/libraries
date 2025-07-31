#!/usr/bin/env python3
"""
Script para contar el total de líneas de productos en Odoo
que deberían coincidir con los registros sincronizados en la DB
"""

import sys
import os
from datetime import datetime, date
from config_manager import secrets
from odoo_api.sales import OdooSales

def count_total_order_lines():
    """Cuenta el total de líneas de productos en Odoo con los mismos filtros del Sales Engine"""
    
    print("🔍 Conectando a Odoo producción...")
    
    # Obtener configuración de Odoo producción
    config = secrets
    odoo_config = config.get_odoo_config(use_test=False)
    
    # Conectar a Odoo
    odoo_api = OdooSales(
        db=odoo_config['db'],
        url=odoo_config['url'],
        username=odoo_config['username'],
        password=odoo_config['password']
    )
    
    print("✅ Conectado a Odoo!")
    print("📊 Consultando órdenes de venta...")
    
    # Usar los mismos filtros que el Sales Engine
    # Rango completo desde 2016 hasta hoy
    start_date = date(2016, 1, 1)
    end_date = date.today()
    
    # Convertir fechas a UTC usando el método del Sales Engine
    user_tz = odoo_api.get_user_timezone()
    start_utc, end_utc = odoo_api._convert_timezone_range(start_date, end_date, user_tz)
    
    print(f"📅 Rango de fechas: {start_date} a {end_date}")
    print(f"🕐 UTC: {start_utc} a {end_utc}")
    
    # Consultar órdenes de venta con los mismos filtros
    sales_domain = [
        ('state', 'in', ['sale', 'done']),
        ('invoice_status', '=', 'invoiced'),
        ('date_order', '>=', start_utc),
        ('date_order', '<=', end_utc)
    ]
    
    print("🔎 Aplicando filtros:")
    print("   - Estado: ['sale', 'done'] (Orden de Venta, Completamente Facturado)")
    print("   - Estado Facturación: 'invoiced' (Facturado)")
    print(f"   - Fecha Orden: >= {start_utc}")
    print(f"   - Fecha Orden: <= {end_utc}")
    
    # Obtener IDs de órdenes que cumplen los criterios
    order_ids = odoo_api.models.execute_kw(
        odoo_api.db, odoo_api.uid, odoo_api.password,
        'sale.order', 'search', [sales_domain]
    )
    
    total_orders = len(order_ids)
    print(f"📋 Órdenes encontradas: {total_orders:,}")
    
    if total_orders == 0:
        print("⚠️  No se encontraron órdenes")
        return 0, 0
    
    print("🧮 Contando líneas de productos...")
    
    # Contar líneas de productos en lotes para eficiencia
    total_lines = 0
    batch_size = 100
    processed_orders = 0
    
    for i in range(0, len(order_ids), batch_size):
        batch_ids = order_ids[i:i + batch_size]
        
        # Obtener órdenes con sus líneas
        orders = odoo_api.models.execute_kw(
            odoo_api.db, odoo_api.uid, odoo_api.password,
            'sale.order', 'read', [batch_ids], 
            {'fields': ['id', 'name', 'order_line']}
        )
        
        # Contar líneas en este lote
        batch_lines = 0
        for order in orders:
            lines_count = len(order.get('order_line', []))
            batch_lines += lines_count
            processed_orders += 1
        
        total_lines += batch_lines
        
        if processed_orders % 500 == 0 or processed_orders == total_orders:
            print(f"   Procesadas: {processed_orders:,}/{total_orders:,} órdenes - Líneas acumuladas: {total_lines:,}")
    
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL")
    print("="*60)
    print(f"🏪 Total de órdenes de venta: {total_orders:,}")
    print(f"📦 Total de líneas de productos: {total_lines:,}")
    print(f"📈 Promedio de productos por orden: {total_lines/total_orders:.2f}")
    print("="*60)
    
    return total_orders, total_lines

if __name__ == "__main__":
    try:
        orders, lines = count_total_order_lines()
        print(f"\n✅ Este número ({lines:,}) debería coincidir con los registros en tu DB PostgreSQL")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 