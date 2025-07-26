#!/usr/bin/env python3
"""
Script para Aplicar Filtros de Ciclo de Vida

Aplica los filtros de productos descontinuados e inactivos a los 
forecasts existentes en la base de datos.

Funcionalidades:
- 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0
- 📅 Validación temporal: Verificar actividad reciente antes de generar forecast
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sales_engine.db_client import DatabaseReader, ForecastReader
from sales_engine.forecaster.product_lifecycle_validator import ProductLifecycleValidator, ProductStatus


def apply_filters_to_existing_forecasts(month: int = 1, save_to_db: bool = False):
    """
    Aplicar filtros de ciclo de vida a forecasts existentes.
    
    Args:
        month (int): Mes de forecasts a procesar
        save_to_db (bool): Si guardar las correcciones en la base de datos
    """
    print("🛑 APLICANDO FILTROS DE CICLO DE VIDA A FORECASTS")
    print("=" * 60)
    
    # Inicializar componentes
    db_reader = DatabaseReader()
    forecast_reader = ForecastReader()
    validator = ProductLifecycleValidator(
        discontinued_threshold_days=365,  # 12 meses
        inactive_threshold_days=180,      # 6 meses
        minimum_historical_sales=10
    )
    
    # 1. Obtener forecasts actuales
    print(f"📊 Obteniendo forecasts para el mes {month}...")
    current_forecasts = forecast_reader.get_forecasts_by_month(month)
    
    if not current_forecasts:
        print("❌ No se encontraron forecasts para procesar")
        return
    
    print(f"   Forecasts encontrados: {len(current_forecasts)}")
    print(f"   Total forecast actual: {sum(current_forecasts.values()):,.1f} unidades")
    
    # 2. Obtener historiales de ventas para todos los SKUs
    print(f"📅 Obteniendo historiales de ventas...")
    skus_with_forecasts = list(current_forecasts.keys())
    
    # Procesar en lotes para evitar timeouts
    batch_size = 50
    all_histories = {}
    
    for i in range(0, len(skus_with_forecasts), batch_size):
        batch_skus = skus_with_forecasts[i:i+batch_size]
        print(f"   Procesando lote {i//batch_size + 1}/{(len(skus_with_forecasts)-1)//batch_size + 1}")
        
        for sku in batch_skus:
            try:
                history = db_reader.get_sales_data(product_skus=[sku])
                all_histories[sku] = history
            except Exception as e:
                print(f"   ⚠️  Error obteniendo historial para SKU {sku}: {e}")
                all_histories[sku] = pd.DataFrame()
    
    # 3. Validar productos
    print(f"🔍 Validando {len(all_histories)} productos...")
    validation_results = validator.batch_validate_products(all_histories)
    
    # 4. Generar resumen de validación
    summary = validator.get_validation_summary(validation_results)
    
    print(f"\n📋 RESUMEN DE VALIDACIÓN:")
    print("-" * 50)
    print(f"   Total productos: {summary['total_products']}")
    print(f"   Deben generar forecast: {summary['should_forecast']}")
    print(f"   NO deben generar forecast: {summary['should_not_forecast']}")
    
    for status, count in summary['by_status'].items():
        print(f"   {status.upper()}: {count} productos")
    
    # 5. Aplicar filtros a forecasts
    print(f"\n🔧 APLICANDO CORRECCIONES...")
    corrected_forecasts = validator.apply_lifecycle_filters_to_forecasts(
        current_forecasts, validation_results
    )
    
    # 6. Calcular impacto de las correcciones
    total_original = sum(current_forecasts.values())
    total_corrected = sum(corrected_forecasts.values())
    total_reduction = total_original - total_corrected
    reduction_pct = (total_reduction / total_original * 100) if total_original > 0 else 0
    
    print(f"\n💰 IMPACTO DE LAS CORRECCIONES:")
    print("-" * 50)
    print(f"   Forecast original total: {total_original:,.1f} unidades")
    print(f"   Forecast corregido total: {total_corrected:,.1f} unidades")
    print(f"   Reducción total: {total_reduction:,.1f} unidades ({reduction_pct:.1f}%)")
    
    # 7. Mostrar productos más afectados
    corrections = []
    for sku in current_forecasts:
        original = current_forecasts[sku]
        corrected = corrected_forecasts.get(sku, original)
        if original != corrected:
            reduction = original - corrected
            corrections.append({
                'sku': sku,
                'original': original,
                'corrected': corrected,
                'reduction': reduction,
                'status': validation_results.get(sku, {}).get('status', 'unknown'),
                'reason': validation_results.get(sku, {}).get('metadata', {}).get('reason', 'N/A')
            })
    
    if corrections:
        corrections_df = pd.DataFrame(corrections)
        corrections_df = corrections_df.sort_values('reduction', ascending=False)
        
        print(f"\n🚨 TOP 15 PRODUCTOS CON MAYORES CORRECCIONES:")
        print("-" * 90)
        print(f"{'SKU':<8} {'Original':<10} {'Corregido':<10} {'Reducción':<10} {'Estado':<15} {'Razón':<25}")
        print("-" * 90)
        
        for _, row in corrections_df.head(15).iterrows():
            status_display = row['status'].value if hasattr(row['status'], 'value') else str(row['status'])
            reason_short = row['reason'][:24] + "..." if len(row['reason']) > 24 else row['reason']
            print(f"{row['sku']:<8} {row['original']:<10.1f} {row['corrected']:<10.1f} "
                  f"{row['reduction']:<10.1f} {status_display:<15} {reason_short:<25}")
    
    # 8. Estadísticas por estado
    status_stats = {}
    for sku, result in validation_results.items():
        status = result['status'].value
        if status not in status_stats:
            status_stats[status] = {'count': 0, 'original_forecast': 0, 'corrected_forecast': 0}
        
        status_stats[status]['count'] += 1
        status_stats[status]['original_forecast'] += current_forecasts.get(sku, 0)
        status_stats[status]['corrected_forecast'] += corrected_forecasts.get(sku, 0)
    
    print(f"\n📊 ESTADÍSTICAS POR ESTADO:")
    print("-" * 70)
    print(f"{'Estado':<15} {'Productos':<10} {'Forecast Orig':<15} {'Forecast Corr':<15} {'Reducción':<10}")
    print("-" * 70)
    
    for status, stats in status_stats.items():
        reduction = stats['original_forecast'] - stats['corrected_forecast']
        print(f"{status:<15} {stats['count']:<10} {stats['original_forecast']:<15.1f} "
              f"{stats['corrected_forecast']:<15.1f} {reduction:<10.1f}")
    
    # 9. Guardar resultados si se solicita
    if save_to_db:
        print(f"\n💾 GUARDANDO CORRECCIONES EN BASE DE DATOS...")
        # Aquí se implementaría la lógica para actualizar la tabla de forecasts
        # Por ahora, solo mostramos un mensaje
        print("   ⚠️  Funcionalidad de guardado no implementada aún")
        print("   💡 Se requiere implementar DatabaseUpdater.update_forecasts()")
    
    return {
        'original_forecasts': current_forecasts,
        'corrected_forecasts': corrected_forecasts,
        'validation_results': validation_results,
        'corrections_df': corrections_df if corrections else pd.DataFrame(),
        'summary': summary
    }


def main():
    """Función principal."""
    
    print("🛑 APLICADOR DE FILTROS DE CICLO DE VIDA PARA FORECASTS")
    print("=" * 70)
    print("Implementa:")
    print("• 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0")
    print("• 📅 Validación temporal: Verificar actividad reciente")
    print("• 🔧 Correcciones automáticas basadas en estado del producto")
    
    # Aplicar filtros para enero
    result = apply_filters_to_existing_forecasts(month=1, save_to_db=False)
    
    if result:
        print(f"\n✅ PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 50)
        
        total_products = len(result['original_forecasts'])
        corrections_made = len(result['corrections_df'])
        total_reduction = sum(result['original_forecasts'].values()) - sum(result['corrected_forecasts'].values())
        
        print(f"📊 Resumen final:")
        print(f"   • Productos analizados: {total_products}")
        print(f"   • Correcciones aplicadas: {corrections_made}")
        print(f"   • Reducción total de forecast: {total_reduction:,.1f} unidades")
        
        if corrections_made > 0:
            print(f"\n🎯 IMPACTO POSITIVO:")
            print(f"   • Se evitará la producción innecesaria de productos descontinuados")
            print(f"   • Mejor precisión en planificación de inventario")
            print(f"   • Recursos de producción optimizados")
        
        print(f"\n💡 PRÓXIMOS PASOS:")
        print(f"   1. Revisar las correcciones propuestas")
        print(f"   2. Validar productos marcados como descontinuados")
        print(f"   3. Integrar filtros en el proceso de generación de forecasts")
        print(f"   4. Programar revisiones periódicas del estado de productos")


if __name__ == "__main__":
    main() 