#!/usr/bin/env python3
"""
Script de ejemplo para obtener datos de ventas por mes

Demuestra cómo usar DatabaseReader para obtener ventas de todos los SKUs
en un mes específico.
"""

import sys
from pathlib import Path
from datetime import date
from calendar import monthrange
import pandas as pd

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "odoo-api" / "src"))

from sales_engine.db_client import DatabaseReader, get_forecasts_by_month
from odoo_api.warehouses import OdooWarehouse
from config_manager import secrets


def get_sales_by_month(year: int, month: int):
    """
    Obtener ventas de todos los SKUs para un mes específico.
    
    Args:
        year (int): Año (ej: 2024)
        month (int): Mes (1-12)
    
    Returns:
        pd.DataFrame: Datos de ventas del mes
    """
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


def analyze_month_sales(year: int, month: int):
    """Analizar ventas de un mes específico."""
    
    month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    print(f"\n🔍 ANÁLISIS DE VENTAS - {month_names[month]} {year}")
    print("=" * 60)
    
    try:
        # Obtener datos de ventas
        sales_data = get_sales_by_month(year, month)
        
        if sales_data.empty:
            print("❌ No se encontraron datos de ventas para este período")
            return
        
        # Resumen general
        print(f"\n📊 Resumen General:")
        print(f"   Total registros: {len(sales_data):,}")
        print(f"   SKUs únicos: {sales_data['items_product_sku'].nunique():,}")
        print(f"   Clientes únicos: {sales_data['customer_customerid'].nunique():,}")
        print(f"   Facturas únicas: {sales_data['salesinvoiceid'].nunique():,}")
        
        # Ventas por SKU
        if 'items_quantity' in sales_data.columns:
            sales_by_sku = sales_data.groupby('items_product_sku').agg({
                'items_quantity': 'sum',
                'salesinvoiceid': 'nunique'
            }).round(2)
            sales_by_sku.columns = ['total_quantity', 'num_invoices']
            
            # Top 10 SKUs
            top_skus = sales_by_sku.nlargest(10, 'total_quantity')
            print(f"\n🏆 Top 10 SKUs por Cantidad Vendida:")
            print("-" * 50)
            for i, (sku, row) in enumerate(top_skus.iterrows(), 1):
                print(f"   {i:2}. {sku}: {row['total_quantity']:8.1f} unidades ({row['num_invoices']} facturas)")
            
            # Estadísticas
            total_quantity = sales_by_sku['total_quantity'].sum()
            avg_quantity = sales_by_sku['total_quantity'].mean()
            
            print(f"\n📈 Estadísticas:")
            print(f"   Total cantidad vendida: {total_quantity:,.1f} unidades")
            print(f"   Promedio por SKU: {avg_quantity:.1f} unidades")
            print(f"   SKUs con ventas > 100: {len(sales_by_sku[sales_by_sku['total_quantity'] > 100])}")
            
            return sales_by_sku
        else:
            print("⚠️  Columna 'items_quantity' no encontrada en los datos")
            print(f"   Columnas disponibles: {list(sales_data.columns)}")
            return sales_data
        
    except Exception as e:
        print(f"❌ Error analizando ventas: {e}")
        return None


def compare_sales_vs_forecast(year: int, month: int):
    """Comparar ventas reales vs forecasts para un mes."""
    
    print(f"\n🔄 COMPARACIÓN: VENTAS REALES vs FORECASTS")
    print("=" * 60)
    
    try:
        # Obtener ventas reales
        sales_data = get_sales_by_month(year, month)
        
        if sales_data.empty or 'items_quantity' not in sales_data.columns:
            print("❌ No hay datos de ventas válidos para comparar")
            return
        
        real_by_sku = sales_data.groupby('items_product_sku')['items_quantity'].sum()
        
        # Obtener forecasts
        forecasts = get_forecasts_by_month(month)
        
        # Crear comparación
        comparison = pd.DataFrame({
            'real_sales': real_by_sku,
            'forecast': pd.Series(forecasts)
        }).fillna(0)
        
        # Calcular métricas
        comparison['difference'] = comparison['forecast'] - comparison['real_sales']
        comparison['abs_difference'] = abs(comparison['difference'])
        
        # Accuracy donde hay ventas reales
        mask = comparison['real_sales'] > 0
        comparison.loc[mask, 'accuracy'] = (
            1 - comparison.loc[mask, 'abs_difference'] / comparison.loc[mask, 'real_sales']
        ) * 100
        
        # Resumen
        total_real = comparison['real_sales'].sum()
        total_forecast = comparison['forecast'].sum()
        
        # Calcular métricas adicionales
        avg_abs_difference = comparison['abs_difference'].mean()
        median_abs_difference = comparison['abs_difference'].median()
        
        print(f"📊 Resumen de Comparación:")
        print(f"   Total ventas reales: {total_real:,.1f} unidades")
        print(f"   Total forecasts: {total_forecast:,.1f} unidades")
        print(f"   Diferencia total: {total_forecast - total_real:+,.1f} unidades")
        print(f"   Accuracy promedio: {comparison['accuracy'].mean():.1f}%")
        print(f"   Diferencia absoluta promedio: {avg_abs_difference:.1f} unidades")
        print(f"   Diferencia absoluta mediana: {median_abs_difference:.1f} unidades")
        
        # Top diferencias
        biggest_diffs = comparison.nlargest(5, 'abs_difference')
        print(f"\n⚠️  Mayores Diferencias (Real vs Forecast):")
        print("-" * 55)
        for sku, row in biggest_diffs.iterrows():
            real = row['real_sales']
            forecast = row['forecast']
            diff = row['difference']
            print(f"   {sku}: Real {real:6.1f} | Forecast {forecast:6.1f} | Diff {diff:+7.1f}")
        
        return comparison
        
    except Exception as e:
        print(f"❌ Error en comparación: {e}")
        return None


def main():
    """Función principal de ejemplo."""
    
    print("🎯 Análisis de Ventas por Mes")
    print("=" * 50)
    
    # Ejemplo 1: Analizar ventas de enero 2024
    sales_summary = analyze_month_sales(2024, 1)
    
    # Ejemplo 2: Comparar con forecasts
    if sales_summary is not None:
        comparison = compare_sales_vs_forecast(2024, 1)
    
    # Ejemplo 3: Múltiples meses
    print(f"\n📊 COMPARACIÓN ESTACIONAL")
    print("=" * 50)
    
    months_to_analyze = [1, 4, 7, 10]  # Enero, Abril, Julio, Octubre
    month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    for month in months_to_analyze:
        try:
            sales_data = get_sales_by_month(2024, month)
            if not sales_data.empty and 'items_quantity' in sales_data.columns:
                total_quantity = sales_data['items_quantity'].sum()
                unique_skus = sales_data['items_product_sku'].nunique()
                print(f"   {month_names[month]:12}: {total_quantity:8,.1f} unidades ({unique_skus} SKUs)")
            else:
                print(f"   {month_names[month]:12}: Sin datos")
        except Exception as e:
            print(f"   {month_names[month]:12}: Error - {e}")
    
    # Ejemplo 4: Calcular cantidades de producción para enero 2024
    print(f"\n" + "="*70)
    print("🏭 EJEMPLO: CÁLCULO DE CANTIDADES DE PRODUCCIÓN")
    print("="*70)
    production_df = calculate_production_quantities(2024, 1, use_test_odoo=False)


def calculate_production_quantities(year: int = None, month: int = None, use_test_odoo: bool = False):
    """
    Calcular la cantidad a producir por SKU basado en:
    Cantidad a producir = Forecast - Ventas del mes actual - Inventario actual
    
    Args:
        year (int): Año (por defecto usa el año actual)
        month (int): Mes (por defecto usa el mes actual)
        use_test_odoo (bool): Si usar el entorno de test de Odoo (por defecto False)
    
    Returns:
        pd.DataFrame: Datos de producción requerida por SKU
    """
    from datetime import datetime
    
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
        
        # Obtener configuración de Odoo
        try:
            odoo_config = secrets.get_odoo_config(use_test=use_test_odoo)
            odoo_warehouse = OdooWarehouse(
                db=odoo_config['db'],
                url=odoo_config['url'],
                username=odoo_config['username'],
                password=odoo_config['password']
            )
        except Exception as e:
            print(f"❌ Error conectando a Odoo: {e}")
            print("💡 Nota: Se requiere configuración de Odoo en config_manager")
            return None
        
        # Obtener todos los SKUs únicos de forecasts y ventas
        all_skus = set(forecasts.keys()) | set(sales_by_sku.index)
        all_skus = list(all_skus)
        
        print(f"   Consultando inventario para {len(all_skus)} SKUs...")
        
        # Obtener inventario para todos los SKUs (usar batch para eficiencia)
        inventory_data = {}
        batch_size = 50  # Procesar en lotes para evitar timeouts
        
        for i in range(0, len(all_skus), batch_size):
            batch_skus = all_skus[i:i+batch_size]
            try:
                batch_inventory = odoo_warehouse.get_stock_by_sku(batch_skus)
                inventory_data.update(batch_inventory)
                print(f"   Procesado lote {i//batch_size + 1}/{(len(all_skus)-1)//batch_size + 1}")
            except Exception as e:
                print(f"   ⚠️  Error en lote {i//batch_size + 1}: {e}")
                # Continuar con el siguiente lote
                continue
        
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


if __name__ == "__main__":
    main() 