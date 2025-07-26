#!/usr/bin/env python3
"""
Script para calcular cantidades de producción requeridas

Calcula: Cantidad a producir = Forecast - Ventas del mes - Inventario actual
Este script funciona con los forecasts generados por el sistema mejorado de lifecycle validation.
"""

import sys
from pathlib import Path
from datetime import datetime

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "odoo-api" / "src"))

from test_sales_by_month import calculate_production_quantities
from sales_engine.forecaster import save_production_forecast


def save_to_database(production_df, year: int, month: int) -> bool:
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
    """Función principal para calcular producción."""
    
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