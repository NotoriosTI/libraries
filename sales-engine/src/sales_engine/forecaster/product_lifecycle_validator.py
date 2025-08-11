"""
Validador de Ciclo de Vida de Productos

Este módulo proporciona funcionalidades para validar si un producto
está activo, descontinuado o inactivo antes de generar forecasts.

Implementa:
- 🛑 Filtro de descontinuados: Si última venta > 12 meses → forecast = 0
- 📅 Validación temporal: Verificar actividad reciente antes de generar forecast
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import pandas as pd
from enum import Enum

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("product-lifecycle-validator")
except ImportError:
    class LoggerFallback:
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️  {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
    logger = LoggerFallback()


class ProductStatus(Enum):
    """Estados posibles de un producto."""
    ACTIVE = "active"
    INACTIVE = "inactive" 
    DISCONTINUED = "discontinued"
    NEW = "new"
    UNKNOWN = "unknown"


class ProductLifecycleValidator:
    """
    Validador de ciclo de vida de productos para el sistema de forecasting.
    
    Evalúa el estado de los productos basándose en su historial de ventas
    para determinar si deben generar forecasts o no.
    """
    
    def __init__(self, 
                 discontinued_threshold_days: int = 365,
                 inactive_threshold_days: int = 180,
                 minimum_historical_sales: float = 10,
                 new_product_threshold_days: int = 90):
        """
        Inicializar el validador con umbrales configurables.
        
        Args:
            discontinued_threshold_days (int): Días sin ventas para considerar descontinuado
            inactive_threshold_days (int): Días sin ventas para considerar inactivo
            minimum_historical_sales (float): Ventas mínimas históricas para ser considerado
            new_product_threshold_days (int): Días desde primera venta para considerar nuevo
        """
        self.discontinued_threshold = discontinued_threshold_days
        self.inactive_threshold = inactive_threshold_days 
        self.minimum_historical_sales = minimum_historical_sales
        self.new_product_threshold = new_product_threshold_days
        
        logger.info("ProductLifecycleValidator inicializado",
                   discontinued_threshold=self.discontinued_threshold,
                   inactive_threshold=self.inactive_threshold)
    
    def validate_product_for_forecasting(self, 
                                       sku: str, 
                                       sales_history: pd.DataFrame) -> Tuple[ProductStatus, Dict]:
        """
        Validar si un producto debe generar forecast basándose en su historial.
        
        Args:
            sku (str): SKU del producto
            sales_history (pd.DataFrame): Historial de ventas con columnas 'issueddate' e 'items_quantity'
        
        Returns:
            Tuple[ProductStatus, Dict]: Estado del producto y metadata de la validación
        """
        # Validar DataFrame vacío
        if sales_history.empty:
            return ProductStatus.UNKNOWN, {
                'reason': 'Sin historial de ventas',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
        
        # Validar que existan las columnas requeridas
        required_columns = ['issueddate', 'items_quantity']
        missing_columns = [col for col in required_columns if col not in sales_history.columns]
        
        if missing_columns:
            logger.error(f"Columnas faltantes para SKU {sku}: {missing_columns}")
            logger.error(f"Columnas disponibles: {list(sales_history.columns)}")
            return ProductStatus.UNKNOWN, {
                'reason': f'Columnas faltantes: {missing_columns}',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
        
        # Validar que no haya valores nulos en columnas críticas
        if sales_history['issueddate'].isnull().all():
            return ProductStatus.UNKNOWN, {
                'reason': 'Todas las fechas son nulas',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
        
        # Limpiar datos: remover filas con fechas nulas
        sales_history_clean = sales_history.dropna(subset=['issueddate']).copy()
        
        if sales_history_clean.empty:
            return ProductStatus.UNKNOWN, {
                'reason': 'Sin fechas válidas después de limpieza',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
        
        # Convertir fechas si es necesario
        try:
            if sales_history_clean['issueddate'].dtype == 'object':
                sales_history_clean['issueddate'] = pd.to_datetime(sales_history_clean['issueddate'])
        except Exception as e:
            logger.error(f"Error convirtiendo fechas para SKU {sku}: {e}")
            return ProductStatus.UNKNOWN, {
                'reason': f'Error en conversión de fechas: {e}',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
        
        # Calcular métricas básicas
        try:
            now = datetime.now()
            last_sale_date = sales_history_clean['issueddate'].max()
            first_sale_date = sales_history_clean['issueddate'].min()
            days_since_last_sale = (now.date() - last_sale_date.date()).days
            days_since_first_sale = (now.date() - first_sale_date.date()).days
            total_sales = sales_history_clean['items_quantity'].sum()
            
            # Ventas recientes (últimos 2 años)
            recent_cutoff = now - timedelta(days=730)
            recent_sales = sales_history_clean[sales_history_clean['issueddate'] >= recent_cutoff]
            recent_total = recent_sales['items_quantity'].sum() if not recent_sales.empty else 0
            
            # Determinar estado del producto
            status, metadata = self._classify_product_status(
                sku=sku,
                days_since_last_sale=days_since_last_sale,
                days_since_first_sale=days_since_first_sale,
                total_sales=total_sales,
                recent_sales=recent_total
            )
            
            # Agregar información adicional
            metadata.update({
                'last_sale_date': last_sale_date.date(),
                'first_sale_date': first_sale_date.date(),
                'last_sale_days': days_since_last_sale,
                'total_historical_sales': total_sales,
                'recent_sales_2y': recent_total
            })
            
            return status, metadata
        except Exception as e:
            logger.error(f"Error general en validate_product_for_forecasting para SKU {sku}: {e}")
            return ProductStatus.UNKNOWN, {
                'reason': f'Error general en validación: {e}',
                'should_forecast': False,
                'recommended_forecast': 0,
                'last_sale_days': None,
                'total_historical_sales': 0
            }
    
    def _classify_product_status(self, 
                               sku: str,
                               days_since_last_sale: int,
                               days_since_first_sale: int, 
                               total_sales: float,
                               recent_sales: float) -> Tuple[ProductStatus, Dict]:
        """Clasificar el estado del producto basándose en las métricas."""
        
        # 🛑 FILTRO PRINCIPAL: Productos descontinuados
        if days_since_last_sale > self.discontinued_threshold:
            return ProductStatus.DISCONTINUED, {
                'reason': f'Sin ventas por {days_since_last_sale} días (>{self.discontinued_threshold})',
                'should_forecast': False,
                'recommended_forecast': 0,
                'confidence': 'HIGH'
            }
        
        # 📅 VALIDACIÓN TEMPORAL: Productos inactivos
        if days_since_last_sale > self.inactive_threshold:
            # Permitir forecast mínimo solo si tiene historial significativo
            if total_sales >= self.minimum_historical_sales:
                recommended = min(5, total_sales / (days_since_first_sale / 30) * 0.1)
            else:
                recommended = 0
                
            return ProductStatus.INACTIVE, {
                'reason': f'Inactivo por {days_since_last_sale} días (>{self.inactive_threshold})',
                'should_forecast': recommended > 0,
                'recommended_forecast': round(recommended, 1),
                'confidence': 'MEDIUM'
            }
        
        # 🆕 Productos nuevos
        if days_since_first_sale < self.new_product_threshold:
            return ProductStatus.NEW, {
                'reason': f'Producto nuevo ({days_since_first_sale} días desde primera venta)',
                'should_forecast': True,
                'recommended_forecast': None,  # Usar forecast normal pero con precaución
                'confidence': 'LOW'
            }
        
        # ✅ Productos activos
        if recent_sales > 0:
            return ProductStatus.ACTIVE, {
                'reason': f'Producto activo (ventas recientes: {recent_sales})',
                'should_forecast': True,
                'recommended_forecast': None,  # Usar forecast normal
                'confidence': 'HIGH'
            }
        
        # 🤔 Productos sin ventas recientes pero no descontinuados
        return ProductStatus.INACTIVE, {
            'reason': 'Sin ventas recientes pero dentro del umbral',
            'should_forecast': False,
            'recommended_forecast': 0,
            'confidence': 'MEDIUM'
        }
    
    def batch_validate_products(self, 
                              skus_with_history: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        Validar múltiples productos en lote.
        
        Args:
            skus_with_history (Dict[str, pd.DataFrame]): Diccionario con SKU como clave 
                                                        y DataFrame de historial como valor
        
        Returns:
            Dict[str, Dict]: Resultados de validación por SKU
        """
        results = {}
        stats = {
            'total': len(skus_with_history),
            'active': 0,
            'inactive': 0, 
            'discontinued': 0,
            'new': 0,
            'unknown': 0
        }
        
        logger.info(f"Validando {len(skus_with_history)} productos...")
        
        for sku, history in skus_with_history.items():
            try:
                status, metadata = self.validate_product_for_forecasting(sku, history)
                
                results[sku] = {
                    'status': status,
                    'metadata': metadata
                }
                
                # Actualizar estadísticas
                stats[status.value] += 1
                
            except Exception as e:
                logger.error(f"Error validando SKU {sku}: {e}")
                results[sku] = {
                    'status': ProductStatus.UNKNOWN,
                    'metadata': {
                        'reason': f'Error en validación: {e}',
                        'should_forecast': False,
                        'recommended_forecast': 0
                    }
                }
                stats['unknown'] += 1
        
        # Log de estadísticas
        logger.info("Validación completada", **stats)
        
        return results
    
    def get_validation_summary(self, validation_results: Dict[str, Dict]) -> Dict:
        """Generar resumen de resultados de validación."""
        
        summary = {
            'total_products': len(validation_results),
            'should_forecast': 0,
            'should_not_forecast': 0,
            'by_status': {},
            'discontinued_savings': 0
        }
        
        for sku, result in validation_results.items():
            status = result['status']
            metadata = result['metadata']
            
            # Contar por estado
            if status.value not in summary['by_status']:
                summary['by_status'][status.value] = 0
            summary['by_status'][status.value] += 1
            
            # Contar forecasting recomendations
            if metadata.get('should_forecast', False):
                summary['should_forecast'] += 1
            else:
                summary['should_not_forecast'] += 1
        
        return summary
    
    def apply_lifecycle_filters_to_forecasts(self, 
                                           current_forecasts: Dict[str, float],
                                           validation_results: Dict[str, Dict]) -> Dict[str, float]:
        """
        Aplicar filtros de ciclo de vida a forecasts existentes.
        
        Args:
            current_forecasts (Dict[str, float]): Forecasts actuales por SKU
            validation_results (Dict[str, Dict]): Resultados de validación
            
        Returns:
            Dict[str, float]: Forecasts corregidos
        """
        corrected_forecasts = {}
        corrections_applied = 0
        total_reduction = 0
        
        for sku, current_forecast in current_forecasts.items():
            if sku in validation_results:
                validation = validation_results[sku]
                metadata = validation['metadata']
                
                if not metadata.get('should_forecast', True):
                    # Aplicar corrección
                    recommended = metadata.get('recommended_forecast', 0)
                    corrected_forecasts[sku] = recommended
                    
                    if recommended != current_forecast:
                        corrections_applied += 1
                        total_reduction += (current_forecast - recommended)
                        
                        logger.info(f"Forecast corregido para SKU {sku}",
                                  original=current_forecast,
                                  corrected=recommended, 
                                  reason=metadata.get('reason', 'N/A'))
                else:
                    # Mantener forecast original
                    corrected_forecasts[sku] = current_forecast
            else:
                # Sin validación, mantener original
                corrected_forecasts[sku] = current_forecast
        
        logger.success(f"Filtros aplicados",
                      corrections=corrections_applied,
                      total_reduction=total_reduction)
        
        return corrected_forecasts 