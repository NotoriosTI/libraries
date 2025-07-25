#!/usr/bin/env python3
"""
Script Rápido para Ejecutar Backtesting

Ejecuta la comparación de modelos de forecasting de forma simplificada.
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtesting_comparison import BacktestingComparison

def main():
    """Ejecutar backtesting de forma simple."""
    
    print("🚀 Ejecutando Backtesting de Modelos de Forecasting...")
    print("   📊 Comparando: SARIMA vs Regresión Lineal")
    print("   📅 Enfoque: Todos los meses vs Mismo mes histórico")
    
    try:
        # Ejecutar backtesting
        backtester = BacktestingComparison()
        metrics_df, all_results = backtester.run_full_backtesting()
        
        # Guardar y mostrar resultados
        backtester.save_results(metrics_df, all_results)
        backtester.display_results(metrics_df)
        
        print("\n✅ ¡Backtesting completado exitosamente!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 