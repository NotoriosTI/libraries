#!/usr/bin/env python3
"""
Script para verificar que el filtro de cotizaciones funciona
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sales_engine.forecaster.sales_forcaster import SalesForecaster

def verify_cotizaciones_fix():
    """Verificar que las cotizaciones fueron filtradas correctamente"""
    print("🔍 VERIFICACIÓN: Filtro de Cotizaciones")
    print("="*50)
    
    forecaster = SalesForecaster()
    
    # Obtener datos con el nuevo filtro
    print("\n📥 Obteniendo datos históricos (SIN cotizaciones)...")
    historical_data = forecaster.get_historical_sales_data()
    
    if historical_data is None:
        print("❌ No se pudieron obtener datos")
        return
        
    print(f"✅ Datos obtenidos: {len(historical_data):,} registros")
    
    # Verificar SKU 6889 específicamente
    sku_6889_data = historical_data[historical_data['items_product_sku'] == '6889']
    print(f"📊 Registros SKU 6889: {len(sku_6889_data):,}")
    
    # Preparar series temporales
    monthly_data = forecaster.prepare_monthly_time_series(historical_data)
    sku_6889_monthly = monthly_data[monthly_data['sku'] == '6889']
    
    if len(sku_6889_monthly) > 0:
        print(f"📅 Datos mensuales SKU 6889: {len(sku_6889_monthly)} meses")
        
        # Ver nov-dic 2024
        nov_dec_2024 = sku_6889_monthly[
            (sku_6889_monthly['month'] >= '2024-11-01') & 
            (sku_6889_monthly['month'] <= '2024-12-31')
        ]
        
        print(f"\n📊 Nov-Dic 2024 (después del filtro):")
        for _, row in nov_dec_2024.iterrows():
            print(f"   📅 {row['month']}: {row['total_quantity']} unidades")
            
        # Verificar que no hay picos masivos
        max_monthly = sku_6889_monthly['total_quantity'].max()
        print(f"\n📈 Máximo mensual SKU 6889: {max_monthly:,} unidades")
        
        if max_monthly < 1000:
            print("✅ ¡ÉXITO! No hay picos anómalos")
        else:
            print("⚠️  Aún hay valores altos, revisar otros canales")
    else:
        print("⚠️  SKU 6889 no encontrado en datos mensuales")

if __name__ == "__main__":
    verify_cotizaciones_fix() 