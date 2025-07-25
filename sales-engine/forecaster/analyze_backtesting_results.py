#!/usr/bin/env python3
"""
Analizador de Resultados de Backtesting

Analiza en detalle los resultados del backtesting de modelos de forecasting,
proporcionando insights adicionales y visualizaciones.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import glob

# Configuración de visualización
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

RESULTS_DIR = Path(__file__).parent / "data" / "backtesting"

class BacktestingAnalyzer:
    """Analizador de resultados de backtesting."""
    
    def __init__(self):
        self.results_dir = RESULTS_DIR
        self.metrics_df = None
        self.detailed_df = None
    
    def load_latest_results(self):
        """Cargar los resultados más recientes."""
        print("📂 Cargando resultados más recientes...")
        
        # Buscar archivos más recientes
        metrics_files = list(self.results_dir.glob("backtesting_metrics_*.csv"))
        detailed_files = list(self.results_dir.glob("backtesting_detailed_*.csv"))
        
        if not metrics_files or not detailed_files:
            print("❌ No se encontraron archivos de resultados")
            return False
        
        # Tomar el más reciente
        latest_metrics = max(metrics_files, key=lambda x: x.stat().st_mtime)
        latest_detailed = max(detailed_files, key=lambda x: x.stat().st_mtime)
        
        self.metrics_df = pd.read_csv(latest_metrics)
        self.detailed_df = pd.read_csv(latest_detailed)
        
        print(f"✅ Cargados resultados de: {latest_metrics.name}")
        print(f"   📊 Métricas: {len(self.metrics_df)} modelos")
        print(f"   📋 Detalles: {len(self.detailed_df)} predicciones")
        
        return True
    
    def show_model_comparison(self):
        """Mostrar comparación detallada de modelos."""
        if self.metrics_df is None:
            print("❌ No hay datos cargados")
            return
        
        print("\n" + "="*80)
        print("📊 COMPARACIÓN DETALLADA DE MODELOS")
        print("="*80)
        
        # Ordenar por variabilidad
        df_sorted = self.metrics_df.sort_values('variability').reset_index(drop=True)
        
        print("\n🏆 RANKING COMPLETO:")
        print("-" * 100)
        print(f"{'Rank':<4} {'Modelo':<18} {'N':<6} {'MAE':<10} {'RMSE':<10} {'MAPE':<10} {'Variabilidad':<12} {'R²':<8}")
        print("-" * 100)
        
        for i, row in df_sorted.iterrows():
            print(f"{i+1:<4} {row['model']:<18} {row['n_predictions']:<6.0f} "
                  f"{row['mae']:<10.2f} {row['rmse']:<10.2f} {row['mape']:<10.1f}% "
                  f"{row['variability']:<12.2f} {row['r2']:<8.3f}")
        
        # Análisis por tipo de modelo
        print(f"\n📈 ANÁLISIS POR TIPO DE MODELO:")
        
        # Agrupar por tipo
        sarima_models = df_sorted[df_sorted['model'].str.contains('sarima')]
        linear_models = df_sorted[df_sorted['model'].str.contains('linear')]
        
        if not sarima_models.empty:
            print(f"\n🔮 MODELOS SARIMA:")
            for _, row in sarima_models.iterrows():
                approach = "Todos los meses" if "all" in row['model'] else "Mismo mes"
                print(f"   • {approach:<15}: Variabilidad={row['variability']:.2f}, MAE={row['mae']:.2f}, R²={row['r2']:.3f}")
        
        if not linear_models.empty:
            print(f"\n📏 MODELOS LINEALES:")
            for _, row in linear_models.iterrows():
                approach = "Todos los meses" if "all" in row['model'] else "Mismo mes"
                print(f"   • {approach:<15}: Variabilidad={row['variability']:.2f}, MAE={row['mae']:.2f}, R²={row['r2']:.3f}")
    
    def analyze_predictions_by_sku(self):
        """Analizar predicciones por SKU."""
        if self.detailed_df is None:
            print("❌ No hay datos detallados cargados")
            return
        
        print(f"\n📦 ANÁLISIS POR SKU:")
        print("-" * 60)
        
        # Calcular errores por SKU y modelo
        sku_analysis = []
        
        for sku in self.detailed_df['sku'].unique():
            sku_data = self.detailed_df[self.detailed_df['sku'] == sku].copy()
            
            # Calcular MAE para cada modelo en este SKU
            models = ['pred_sarima_all', 'pred_sarima_same', 'pred_linear_all', 'pred_linear_same']
            
            for model in models:
                valid_data = sku_data.dropna(subset=[model, 'actual'])
                if len(valid_data) > 0:
                    mae = np.mean(np.abs(valid_data['actual'] - valid_data[model]))
                    mape = np.mean(np.abs((valid_data['actual'] - valid_data[model]) / valid_data['actual'])) * 100
                    
                    sku_analysis.append({
                        'sku': sku,
                        'model': model.replace('pred_', ''),
                        'n_predictions': len(valid_data),
                        'mae': mae,
                        'mape': mape
                    })
        
        sku_df = pd.DataFrame(sku_analysis)
        
        if not sku_df.empty:
            # Mostrar los 5 SKUs con mejor y peor performance
            sku_summary = sku_df.groupby('sku')['mae'].mean().sort_values()
            
            print(f"\n🏆 TOP 5 SKUs con MENOR error promedio:")
            for sku in sku_summary.head().index:
                print(f"   📦 {sku}: MAE promedio = {sku_summary[sku]:.2f}")
            
            print(f"\n⚠️  TOP 5 SKUs con MAYOR error promedio:")
            for sku in sku_summary.tail().index:
                print(f"   📦 {sku}: MAE promedio = {sku_summary[sku]:.2f}")
    
    def analyze_seasonal_performance(self):
        """Analizar performance por estacionalidad."""
        if self.detailed_df is None:
            print("❌ No hay datos detallados cargados")
            return
        
        print(f"\n📅 ANÁLISIS DE PERFORMANCE ESTACIONAL:")
        print("-" * 60)
        
        # Extraer mes de la columna 'month'
        self.detailed_df['month_num'] = pd.to_datetime(self.detailed_df['month']).dt.month
        
        # Calcular MAE por mes para cada modelo
        models = ['pred_sarima_all', 'pred_sarima_same', 'pred_linear_all', 'pred_linear_same']
        
        monthly_performance = {}
        
        for model in models:
            monthly_mae = []
            for month in range(1, 13):
                month_data = self.detailed_df[self.detailed_df['month_num'] == month]
                valid_data = month_data.dropna(subset=[model, 'actual'])
                
                if len(valid_data) > 0:
                    mae = np.mean(np.abs(valid_data['actual'] - valid_data[model]))
                    monthly_mae.append(mae)
                else:
                    monthly_mae.append(np.nan)
            
            monthly_performance[model.replace('pred_', '')] = monthly_mae
        
        # Mostrar resultados
        month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        
        print(f"\n📊 MAE promedio por mes:")
        print(f"{'Mes':<4} {'SARIMA-All':<12} {'SARIMA-Same':<13} {'Linear-All':<12} {'Linear-Same':<12}")
        print("-" * 60)
        
        for i, month in enumerate(month_names):
            sarima_all = monthly_performance['sarima_all'][i]
            sarima_same = monthly_performance['sarima_same'][i]
            linear_all = monthly_performance['linear_all'][i]
            linear_same = monthly_performance['linear_same'][i]
            
            print(f"{month:<4} {sarima_all:<12.2f} {sarima_same:<13.2f} {linear_all:<12.2f} {linear_same:<12.2f}")
    
    def create_visualizations(self):
        """Crear visualizaciones de los resultados."""
        if self.metrics_df is None or self.detailed_df is None:
            print("❌ No hay datos suficientes para visualización")
            return
        
        print(f"\n📈 Creando visualizaciones...")
        
        # Crear figura con subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Análisis de Performance - Backtesting de Modelos', fontsize=16, fontweight='bold')
        
        # 1. Comparación de métricas por modelo
        ax1 = axes[0, 0]
        models = self.metrics_df['model']
        variability = self.metrics_df['variability']
        mae = self.metrics_df['mae']
        
        x_pos = np.arange(len(models))
        ax1.bar(x_pos, variability, alpha=0.7, color='skyblue', label='Variabilidad')
        ax1.set_title('Variabilidad por Modelo')
        ax1.set_xlabel('Modelo')
        ax1.set_ylabel('Variabilidad')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(models, rotation=45, ha='right')
        ax1.grid(True, alpha=0.3)
        
        # 2. MAE vs MAPE
        ax2 = axes[0, 1]
        ax2.scatter(self.metrics_df['mae'], self.metrics_df['mape'], 
                   s=100, alpha=0.7, c=['red', 'blue', 'green', 'orange'])
        
        for i, model in enumerate(self.metrics_df['model']):
            ax2.annotate(model, 
                        (self.metrics_df['mae'].iloc[i], self.metrics_df['mape'].iloc[i]),
                        xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        ax2.set_title('MAE vs MAPE por Modelo')
        ax2.set_xlabel('MAE (Mean Absolute Error)')
        ax2.set_ylabel('MAPE (Mean Absolute Percentage Error %)')
        ax2.grid(True, alpha=0.3)
        
        # 3. Distribución de errores
        ax3 = axes[1, 0]
        
        # Calcular errores absolutos para cada modelo
        models_to_plot = ['pred_sarima_all', 'pred_sarima_same', 'pred_linear_all', 'pred_linear_same']
        errors_data = []
        
        for model in models_to_plot:
            valid_data = self.detailed_df.dropna(subset=[model, 'actual'])
            if len(valid_data) > 0:
                errors = np.abs(valid_data['actual'] - valid_data[model])
                errors_data.append(errors)
            else:
                errors_data.append([])
        
        ax3.boxplot(errors_data, labels=[m.replace('pred_', '') for m in models_to_plot])
        ax3.set_title('Distribución de Errores Absolutos')
        ax3.set_ylabel('Error Absoluto')
        ax3.grid(True, alpha=0.3)
        plt.setp(ax3.get_xticklabels(), rotation=45, ha='right')
        
        # 4. Performance temporal
        ax4 = axes[1, 1]
        
        # Agrupar por mes y calcular MAE promedio
        monthly_data = self.detailed_df.copy()
        monthly_data['month_dt'] = pd.to_datetime(monthly_data['month'])
        monthly_data['month_num'] = monthly_data['month_dt'].dt.month
        
        for model in models_to_plot:
            monthly_mae = []
            months = []
            
            for month in range(1, 13):
                month_data = monthly_data[monthly_data['month_num'] == month]
                valid_data = month_data.dropna(subset=[model, 'actual'])
                
                if len(valid_data) > 0:
                    mae = np.mean(np.abs(valid_data['actual'] - valid_data[model]))
                    monthly_mae.append(mae)
                    months.append(month)
            
            if monthly_mae:
                ax4.plot(months, monthly_mae, marker='o', label=model.replace('pred_', ''), linewidth=2)
        
        ax4.set_title('MAE Promedio por Mes')
        ax4.set_xlabel('Mes')
        ax4.set_ylabel('MAE')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.set_xticks(range(1, 13))
        
        plt.tight_layout()
        
        # Guardar gráfico
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plot_file = self.results_dir / f"backtesting_analysis_{timestamp}.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.show()
        
        print(f"📊 Visualización guardada: {plot_file}")
    
    def generate_summary_report(self):
        """Generar reporte de resumen."""
        if self.metrics_df is None:
            print("❌ No hay datos para generar reporte")
            return
        
        print(f"\n" + "="*80)
        print("📄 REPORTE DE RESUMEN - BACKTESTING")
        print("="*80)
        
        # Mejor modelo por cada métrica
        best_variability = self.metrics_df.loc[self.metrics_df['variability'].idxmin()]
        best_mae = self.metrics_df.loc[self.metrics_df['mae'].idxmin()]
        best_r2 = self.metrics_df.loc[self.metrics_df['r2'].idxmax()]
        
        print(f"\n🏆 MEJORES MODELOS POR MÉTRICA:")
        print(f"   📊 Menor Variabilidad: {best_variability['model']} ({best_variability['variability']:.2f})")
        print(f"   📈 Menor MAE: {best_mae['model']} ({best_mae['mae']:.2f})")
        print(f"   📈 Mejor R²: {best_r2['model']} ({best_r2['r2']:.3f})")
        
        # Recomendación final
        print(f"\n💡 RECOMENDACIÓN:")
        
        # El modelo con menor variabilidad es generalmente el mejor para forecasting
        recommended_model = best_variability['model']
        
        if 'sarima' in recommended_model:
            model_type = "SARIMA"
        else:
            model_type = "Regresión Lineal"
        
        if 'all' in recommended_model:
            approach = "todos los meses"
        else:
            approach = "mismo mes histórico"
        
        print(f"   🎯 Modelo recomendado: {model_type} con {approach}")
        print(f"   📊 Razón: Menor variabilidad en predicciones ({best_variability['variability']:.2f})")
        print(f"   🎯 Esto significa predicciones más consistentes y confiables")
        
        # Insights adicionales
        print(f"\n🔍 INSIGHTS ADICIONALES:")
        
        # Comparar enfoques SARIMA vs Linear
        sarima_avg = self.metrics_df[self.metrics_df['model'].str.contains('sarima')]['variability'].mean()
        linear_avg = self.metrics_df[self.metrics_df['model'].str.contains('linear')]['variability'].mean()
        
        if sarima_avg < linear_avg:
            print(f"   📈 SARIMA supera a Regresión Lineal en consistencia")
        else:
            print(f"   📏 Regresión Lineal supera a SARIMA en consistencia")
        
        # Comparar enfoques "todos los meses" vs "mismo mes"
        all_months_avg = self.metrics_df[self.metrics_df['model'].str.contains('all')]['variability'].mean()
        same_month_avg = self.metrics_df[self.metrics_df['model'].str.contains('same')]['variability'].mean()
        
        if all_months_avg < same_month_avg:
            print(f"   📅 'Todos los meses' supera a 'Mismo mes' en consistencia")
            print(f"   💡 Usar toda la historia captura mejor las tendencias")
        else:
            print(f"   📅 'Mismo mes' supera a 'Todos los meses' en consistencia")
            print(f"   💡 Enfoque estacional es más robusto a eventos anómalos")


def main():
    """Función principal."""
    print("🔍 ANALIZADOR DE RESULTADOS DE BACKTESTING")
    print("=" * 60)
    
    analyzer = BacktestingAnalyzer()
    
    if not analyzer.load_latest_results():
        print("❌ No se pudieron cargar los resultados")
        return 1
    
    # Ejecutar todos los análisis
    analyzer.show_model_comparison()
    analyzer.analyze_predictions_by_sku()
    analyzer.analyze_seasonal_performance()
    analyzer.create_visualizations()
    analyzer.generate_summary_report()
    
    print(f"\n✅ Análisis completado!")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main()) 