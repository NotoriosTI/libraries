#!/usr/bin/env python3
"""
Script Completo de Backtesting

Ejecuta todo el proceso completo:
1. Backtesting de los 4 modelos
2. Análisis detallado de resultados  
3. Visualizaciones
4. Reporte final

Esto responde a la pregunta: ¿Cuál enfoque de forecasting es mejor?
"""

import sys
from pathlib import Path
import time

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Ejecutar proceso completo de backtesting."""
    
    print("🚀 PROCESO COMPLETO DE BACKTESTING")
    print("=" * 70)
    print("Comparando 4 enfoques de forecasting:")
    print("  1. SARIMA con todos los meses")
    print("  2. SARIMA específico al mes a predecir")
    print("  3. Regresión lineal con todos los meses")
    print("  4. Regresión lineal específica al mes a predecir")
    print("=" * 70)
    
    start_time = time.time()
    
    try:
        # PASO 1: Ejecutar backtesting
        print("\n🔬 PASO 1: EJECUTANDO BACKTESTING...")
        print("-" * 50)
        
        from backtesting_comparison import BacktestingComparison
        
        backtester = BacktestingComparison()
        metrics_df, all_results = backtester.run_full_backtesting()
        
        if metrics_df.empty:
            print("❌ No se pudieron generar métricas")
            return 1
        
        # Guardar resultados
        metrics_file, detailed_file = backtester.save_results(metrics_df, all_results)
        
        print(f"\n✅ Backtesting completado!")
        print(f"   📊 Modelos evaluados: {len(metrics_df)}")
        print(f"   📋 Predicciones totales: {len(all_results)}")
        
        # PASO 2: Análisis detallado
        print("\n🔍 PASO 2: ANÁLISIS DETALLADO...")
        print("-" * 50)
        
        from analyze_backtesting_results import BacktestingAnalyzer
        
        analyzer = BacktestingAnalyzer()
        analyzer.metrics_df = metrics_df
        
        # Cargar datos detallados
        import pandas as pd
        analyzer.detailed_df = pd.read_csv(detailed_file)
        
        # Ejecutar análisis
        analyzer.show_model_comparison()
        analyzer.analyze_predictions_by_sku()
        analyzer.analyze_seasonal_performance()
        analyzer.create_visualizations()
        analyzer.generate_summary_report()
        
        # PASO 3: Resumen ejecutivo
        print("\n" + "="*80)
        print("📋 RESUMEN EJECUTIVO")
        print("="*80)
        
        # Obtener el mejor modelo
        best_model = metrics_df.loc[metrics_df['variability'].idxmin()]
        
        print(f"\n🏆 MODELO GANADOR:")
        print(f"   📊 Modelo: {best_model['model']}")
        print(f"   📈 Variabilidad: {best_model['variability']:.2f}")
        print(f"   📈 MAE: {best_model['mae']:.2f}")
        print(f"   📈 MAPE: {best_model['mape']:.1f}%")
        print(f"   📈 R²: {best_model['r2']:.3f}")
        
        # Interpretación para el negocio
        print(f"\n💼 PARA EL NEGOCIO:")
        if 'sarima' in best_model['model']:
            model_type = "SARIMA (modelo de series temporales avanzado)"
        else:
            model_type = "Regresión Lineal (modelo estadístico simple)"
        
        if 'all' in best_model['model']:
            approach = "todos los meses históricos"
            covid_impact = "MÁS afectado por eventos como COVID"
        else:
            approach = "solo el mismo mes de años anteriores"
            covid_impact = "MENOS afectado por eventos como COVID"
        
        print(f"   🎯 Usar {model_type}")
        print(f"   📅 Con datos de {approach}")
        print(f"   🦠 Este enfoque está {covid_impact}")
        print(f"   💡 Variabilidad baja = predicciones más confiables")
        
        # Tiempo total
        total_time = time.time() - start_time
        print(f"\n⏱️  TIEMPO TOTAL: {total_time:.1f} segundos")
        
        print(f"\n📁 ARCHIVOS GENERADOS:")
        print(f"   📊 {metrics_file}")
        print(f"   📋 {detailed_file}")
        print(f"   📈 Visualización en data/backtesting/")
        
        print(f"\n✅ ¡PROCESO COMPLETADO EXITOSAMENTE!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error durante el proceso: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 