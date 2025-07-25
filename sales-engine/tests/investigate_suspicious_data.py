#!/usr/bin/env python3
"""
Script para investigar datos sospechosos de ventas
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
from datetime import datetime, date
from sales_engine.forecaster.sales_forcaster import SalesForecaster

class SuspiciousDataInvestigator:
    def __init__(self):
        self.forecaster = SalesForecaster()
        
    def investigate_sku_6889(self):
        """Investigar el SKU 6889 específicamente en nov-dic 2024"""
        print("🔍 INVESTIGACIÓN DE DATOS SOSPECHOSOS - SKU 6889")
        print("="*70)
        
        # 1. Obtener TODOS los datos originales para SKU 6889
        print("\n📥 1. Obteniendo datos históricos originales...")
        raw_data = self.forecaster.get_historical_sales_data()
        
        if raw_data is None:
            print("❌ No se pudieron obtener datos")
            return
            
        # Filtrar solo SKU 6889
        sku_6889_data = raw_data[raw_data['items_product_sku'] == '6889'].copy()
        
        print(f"✅ Datos encontrados para SKU 6889: {len(sku_6889_data)} registros")
        print(f"📅 Período completo: {sku_6889_data['issueddate'].min()} a {sku_6889_data['issueddate'].max()}")
        
        # 2. Verificar datos sospechosos de nov-dic 2024
        print("\n🚨 2. ANÁLISIS DETALLADO: NOV-DIC 2024")
        print("-" * 50)
        
        # Filtrar nov-dic 2024
        suspicious_period = sku_6889_data[
            (sku_6889_data['issueddate'] >= '2024-11-01') & 
            (sku_6889_data['issueddate'] <= '2024-12-31')
        ].copy()
        
        print(f"📊 Registros en nov-dic 2024: {len(suspicious_period)}")
        
        if len(suspicious_period) > 0:
            print(f"📅 Fechas: {suspicious_period['issueddate'].min()} a {suspicious_period['issueddate'].max()}")
            print(f"🛒 Cantidad total: {suspicious_period['items_quantity'].sum():,}")
            print(f"📈 Cantidad máxima en un día: {suspicious_period['items_quantity'].max():,}")
            print(f"📉 Cantidad mínima en un día: {suspicious_period['items_quantity'].min():,}")
            print(f"📊 Cantidad promedio por día: {suspicious_period['items_quantity'].mean():.1f}")
            
            # Mostrar días con más ventas
            print(f"\n🏆 TOP 10 DÍAS CON MÁS VENTAS:")
            top_days = suspicious_period.nlargest(10, 'items_quantity')[['issueddate', 'items_quantity']]
            for idx, row in top_days.iterrows():
                print(f"   📅 {row['issueddate']}: {row['items_quantity']:,} unidades")
            
            # Agrupar por mes para ver totales mensuales
            print(f"\n📅 TOTALES MENSUALES (nov-dic 2024):")
            suspicious_period['month'] = suspicious_period['issueddate'].dt.to_period('M')
            monthly_totals = suspicious_period.groupby('month')['items_quantity'].sum()
            for month, total in monthly_totals.items():
                print(f"   📊 {month}: {total:,} unidades")
                
        else:
            print("⚠️  No se encontraron registros en nov-dic 2024")
            
        # 3. Comparar con meses normales
        print("\n📊 3. COMPARACIÓN CON MESES NORMALES")
        print("-" * 50)
        
        # Agrupar por mes todos los datos
        sku_6889_data['month'] = sku_6889_data['issueddate'].dt.to_period('M')
        all_monthly_totals = sku_6889_data.groupby('month')['items_quantity'].sum().sort_index()
        
        print("📈 ÚLTIMOS 12 MESES:")
        last_12_months = all_monthly_totals.tail(12)
        for month, total in last_12_months.items():
            status = "🚨" if total > 10000 else "✅" if total > 0 else "⚠️"
            print(f"   {status} {month}: {total:,} unidades")
            
        # 4. Verificar si hay duplicados o patrones extraños
        print(f"\n🔍 4. ANÁLISIS DE PATRONES EXTRAÑOS")
        print("-" * 50)
        
        # Buscar duplicados exactos
        duplicates = sku_6889_data.duplicated(subset=['issueddate', 'items_quantity']).sum()
        print(f"📋 Registros duplicados (misma fecha + cantidad): {duplicates}")
        
        # Buscar transacciones muy grandes
        large_transactions = sku_6889_data[sku_6889_data['items_quantity'] > 1000]
        print(f"🔥 Transacciones > 1,000 unidades: {len(large_transactions)}")
        
        if len(large_transactions) > 0:
            print("📊 Detalle de transacciones grandes:")
            for idx, row in large_transactions.head(10).iterrows():
                print(f"   📅 {row['issueddate']}: {row['items_quantity']:,} unidades")
                
        # 5. Verificar integridad de fechas
        print(f"\n📅 5. VERIFICACIÓN DE FECHAS")
        print("-" * 50)
        
        # Rango de fechas
        date_range = sku_6889_data['issueddate'].max() - sku_6889_data['issueddate'].min()
        print(f"📊 Rango total: {date_range.days} días")
        
        # Fechas futuras
        today = pd.Timestamp.now().date()
        future_dates = sku_6889_data[sku_6889_data['issueddate'].dt.date > today]
        print(f"🔮 Registros con fechas futuras: {len(future_dates)}")
        
        # 6. Revisar la consulta SQL original
        print(f"\n🔍 6. VERIFICAR CONSULTA SQL ORIGINAL")
        print("-" * 50)
        self.check_sql_query()
        
    def check_sql_query(self):
        """Verificar cómo se obtienen los datos originalmente"""
        print("📝 Revisando la consulta SQL que obtiene los datos...")
        
        # Simular query directa
        try:
            with self.forecaster.db_updater.get_connection() as conn:
                # Query específica para SKU 6889 en nov-dic 2024
                query = """
                SELECT 
                    issueddate,
                    items_product_sku,
                    items_quantity,
                    COUNT(*) as record_count
                FROM sales_items 
                WHERE items_product_sku = '6889'
                    AND issueddate >= '2024-11-01'
                    AND issueddate <= '2024-12-31'
                GROUP BY issueddate, items_product_sku, items_quantity
                ORDER BY issueddate, items_quantity DESC
                """
                
                result = pd.read_sql(query, conn)
                
                print(f"📊 Registros únicos en BD: {len(result)}")
                
                if len(result) > 0:
                    print("\n📋 DETALLE DE REGISTROS EN BD:")
                    total_quantity = 0
                    for idx, row in result.iterrows():
                        qty_total = row['items_quantity'] * row['record_count']
                        total_quantity += qty_total
                        print(f"   📅 {row['issueddate']}: {row['items_quantity']} x {row['record_count']} = {qty_total:,} unidades")
                    
                    print(f"\n🧮 TOTAL CALCULADO: {total_quantity:,} unidades")
                else:
                    print("⚠️  No se encontraron registros en la BD para este período")
                    
        except Exception as e:
            print(f"❌ Error al ejecutar query directa: {e}")

if __name__ == "__main__":
    investigator = SuspiciousDataInvestigator()
    investigator.investigate_sku_6889() 