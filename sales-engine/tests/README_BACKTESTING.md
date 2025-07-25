# 🔬 Sistema de Backtesting - Sales Engine

Este directorio contiene el sistema completo de backtesting para comparar diferentes enfoques de forecasting.

## 📁 Archivos Principales

### Core del Sistema
- **`backtesting_comparison.py`** - Clase principal que implementa los 4 enfoques de forecasting
- **`analyze_backtesting_results.py`** - Análisis detallado y visualizaciones de resultados

### Scripts de Ejecución
- **`run_complete_backtesting.py`** - ⭐ **Script principal** - Ejecuta todo el proceso completo
- **`run_backtesting.py`** - Script simplificado para ejecución rápida

## 🚀 Cómo Usar

### Ejecución Completa (Recomendado)
```bash
cd tests
poetry run python run_complete_backtesting.py
```

### Solo Backtesting (Sin análisis)
```bash
cd tests  
poetry run python run_backtesting.py
```

### Solo Análisis (De resultados existentes)
```bash
cd tests
poetry run python analyze_backtesting_results.py
```

## 📊 ¿Qué Hace el Backtesting?

Compara **4 enfoques** de forecasting:

1. **SARIMA con todos los meses** - Usa toda la historia mensual
2. **SARIMA específico al mes** - Solo datos del mismo mes de años anteriores  
3. **Regresión lineal con todos los meses** - Modelo estadístico con historia completa
4. **Regresión lineal específica al mes** - Modelo estadístico por mes

### Métricas Evaluadas
- **Variabilidad** - Consistencia de predicciones (menor = mejor)
- **MAE** - Error absoluto promedio
- **RMSE** - Error cuadrático medio
- **MAPE** - Error porcentual promedio
- **R²** - Coeficiente de determinación

## 📈 Resultados Esperados

### 🏆 Resultado Típico
**Ganador:** SARIMA con todos los meses históricos

**Por qué:**
- ✅ Menor variabilidad (predicciones más consistentes)
- ✅ Menor error absoluto
- ✅ Mejor R² (explica más varianza)
- ✅ Captura tendencias y estacionalidad mejor

### 🤔 Pregunta Clave Respondida
**"¿Usar todos los meses vs mismo mes histórico?"**
- **Todos los meses GANA** - Aprovecha más información
- **Aunque está más afectado por COVID**, sigue siendo superior

## 📁 Archivos Generados

Los resultados se guardan en: `../data/backtesting/`

### Archivos de Salida
- `backtesting_metrics_YYYYMMDD_HHMMSS.csv` - Métricas por modelo
- `backtesting_detailed_YYYYMMDD_HHMMSS.csv` - Predicciones detalladas
- `backtesting_analysis_YYYYMMDD_HHMMSS.png` - Visualizaciones

## ⚙️ Configuración

### Muestras de SKUs
- **Por defecto:** 100 SKUs aleatorios (semilla fija para reproducibilidad)
- **Modifiable en:** `backtesting_comparison.py` línea ~530

### Años de Prueba
- **Por defecto:** [2022, 2023, 2024]
- **Modifiable en:** `backtesting_comparison.py` línea ~45

### Filtros de SKUs
- Mínimo 3 años de historia
- Al menos 24 meses de datos pre-test
- Mínimo 50 unidades vendidas totales

## 🔧 Requisitos Técnicos

### Base de Datos
- PostgreSQL corriendo en `127.0.0.1:5432`
- Base de datos `salesdb` con tabla `sales_items`

### Dependencias Python
```toml
matplotlib (>=3.10.3,<4.0.0)
statsmodels (>=0.14.5,<0.15.0) 
scikit-learn (>=1.7.1,<2.0.0)
seaborn (>=0.13.0,<0.14.0)
pandas (>=2.0.0)
numpy
```

## 📋 Ejemplo de Salida

```
🏆 MODELO GANADOR:
   📊 Modelo: sarima_all
   📈 Variabilidad: 44.63
   📈 MAE: 14.28
   📈 R²: 0.659

💼 PARA EL NEGOCIO:
   🎯 Usar SARIMA (modelo de series temporales avanzado)
   📅 Con datos de todos los meses históricos
   🦠 Este enfoque está MÁS afectado por eventos como COVID
   💡 Variabilidad baja = predicciones más confiables
```

## 🐛 Solución de Problemas

### Error de Base de Datos
```bash
# Verificar que PostgreSQL esté corriendo
brew services start postgresql
# o
sudo systemctl start postgresql
```

### Error de Importación
```bash
# Asegurar que estás en el directorio tests
cd tests
# Verificar que el entorno virtual está activado
poetry shell
```

### Sin Datos Suficientes
- Verificar que hay datos desde 2016 en `sales_items`
- Verificar filtros de SKUs en `filter_skus_for_backtesting()`

---

**Autor:** Sistema automatizado de backtesting  
**Fecha:** 2025-01-25  
**Versión:** 1.0 