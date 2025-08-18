"""
Pipeline simplificado de forecasting unificado

Flujo:
1) Obtener datos de ventas (tabla sales_items)
2) Calcular forecasts de ventas por SKU con máximos históricos
3) Obtener inventario actual desde Odoo
4) Calcular required_production y priority
5) Upsert a tabla forecast unificada

Este módulo simplifica el proceso usando una sola tabla forecast que contiene
tanto la información de forecast como los cálculos de producción requerida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any, List
import time

import pandas as pd

from .sales_forcaster import SalesForecaster
from .generate_all_forecasts import DatabaseForecastUpdater
from .inventory_utils import get_inventory_from_odoo
from config_manager import secrets

# Logger consistente con el resto del proyecto
from dev_utils import PrettyLogger
logger = PrettyLogger("forecast-pipeline")

@dataclass
class PipelineResult:
    year: int
    month: int
    total_skus_forecasted: int
    total_records_upserted: int
    forecast_upsert_stats: Dict[str, Any]


def _sanitize_forecast_keys(all_forecasts: Dict[Any, pd.Series]) -> Dict[str, pd.Series]:
    """Normaliza las claves de SKU a string y filtra valores inválidos (false/true/none/nan/vacíos)."""
    invalid_tokens = {"false", "true", "none", "nan", "null"}
    cleaned: Dict[str, pd.Series] = {}
    for raw_sku, series in all_forecasts.items():
        sku_str = str(raw_sku).strip()
        if not sku_str or sku_str.lower() in invalid_tokens:
            continue
        cleaned[sku_str] = series
    return cleaned


def _extract_monthly_forecast(all_forecasts: Dict[str, pd.Series], year: int, month: int) -> Dict[str, int]:
    """Extrae la cantidad pronosticada por SKU para (year, month) desde las series futuras.

    Retorna un dict sku -> cantidad pronosticada (int) solo para SKUs que tengan valor para ese mes.
    """
    month_forecasts: Dict[str, int] = {}

    for sku, forecast_series in all_forecasts.items():
        try:
            # Asegurar DateTimeIndex para comparar por año/mes
            indexed = forecast_series.copy()
            indexed.index = pd.to_datetime(indexed.index)

            match = indexed[(indexed.index.year == year) & (indexed.index.month == month)]
            if not match.empty:
                value = int(round(float(match.iloc[0])))
                month_forecasts[sku] = max(value, 0)
        except Exception:
            # Si el índice no es convertible, continuar
            continue

    return month_forecasts


def _calculate_priority(forecasted_qty: int, current_stock: float, max_monthly_sales: int) -> str:
    """
    Calcula prioridad según las nuevas heurísticas de rotación.
    
    Args:
        forecasted_qty: Cantidad pronosticada
        current_stock: Stock actual 
        max_monthly_sales: Máximo histórico de ventas mensuales
        
    Returns:
        Prioridad: BAJA, MEDIA, ALTA, CRITICO
    """
    rotation_threshold = 50  # Umbral para distinguir alta/baja rotación
    
    if max_monthly_sales >= rotation_threshold:
        # PRODUCTO DE ALTA ROTACIÓN: usar porcentaje stock/forecast
        if forecasted_qty > 0:
            stock_ratio = current_stock / forecasted_qty
            
            if stock_ratio >= 0.50:
                return "CRITICO"
            elif stock_ratio >= 0.35:
                return "ALTA"
            elif stock_ratio >= 0.20:
                return "MEDIA"
            else:
                return "BAJA"
        else:
            return "BAJA"
    else:
        # PRODUCTO DE BAJA ROTACIÓN: usar valores fijos de required_production
        required_production = max(0, min(forecasted_qty, max_monthly_sales) - int(current_stock))
        
        if required_production >= 40:
            return "CRITICO"
        elif required_production >= 25:
            return "ALTA"
        elif required_production >= 10:
            return "MEDIA"
        else:
            return "BAJA"


def _build_unified_forecast_df(
    monthly_forecasts: Dict[str, int],
    inventory_data: Dict[str, Dict],
    max_sales_data: Dict[str, int],
    unit_prices_data: Dict[str, float],
    year: int,
    month: int
) -> pd.DataFrame:
    """
    Construye el DataFrame unificado para la tabla forecast con todos los campos necesarios.
    
    Args:
        monthly_forecasts: Forecasts por SKU para el mes objetivo
        inventory_data: Datos de inventario desde Odoo
        max_sales_data: Máximo de ventas históricas por SKU
        unit_prices_data: Precios unitarios por SKU
        year: Año del forecast
        month: Mes del forecast
        
    Returns:
        DataFrame con estructura de la nueva tabla forecast
    """
    rows: List[Dict[str, Any]] = []
    
    for sku, forecasted_qty in monthly_forecasts.items():
        # Obtener datos de inventario
        inv_info = inventory_data.get(sku, {})
        if not inv_info.get("found", False):
            # Excluir productos no encontrados en Odoo
            continue
            
        current_stock = float(inv_info.get("qty_available", 0) or 0)
        max_monthly_sales = max_sales_data.get(sku, 0)
        unit_price = unit_prices_data.get(sku, 0.0)
        
        # Aplicar restricción: forecasted_qty no puede exceder max_monthly_sales
        # (esto ya se aplicó en el forecaster, pero por seguridad)
        if max_monthly_sales > 0:
            forecasted_qty = min(forecasted_qty, max_monthly_sales)
        
        # Calcular required_production: MIN(forecasted_qty, max_monthly_sales) - current_stock
        # Pero no menos que 0
        limited_forecast = min(forecasted_qty, max_monthly_sales) if max_monthly_sales > 0 else forecasted_qty
        required_production = max(0, limited_forecast - int(current_stock))
        
        # Calcular prioridad
        priority = _calculate_priority(forecasted_qty, current_stock, max_monthly_sales)
        
        rows.append({
            "sku": sku,
            "year": year,
            "month": month,
            "max_monthly_sales": max_monthly_sales,
            "current_stock": current_stock,
            "forecasted_qty": forecasted_qty,
            "required_production": required_production,
            "unit_price": unit_price,
            "priority": priority
        })
    
    df = pd.DataFrame(rows)
    
    # Ordenar por prioridad y required_production
    priority_order = {"CRITICO": 0, "ALTA": 1, "MEDIA": 2, "BAJA": 3}
    if not df.empty:
        df["_priority_sort"] = df["priority"].map(priority_order)
        df = df.sort_values(["_priority_sort", "required_production"], ascending=[True, False])
        df = df.drop("_priority_sort", axis=1).reset_index(drop=True)
    
    return df


def run_pipeline(year: Optional[int] = None, month: Optional[int] = None, use_test_odoo: bool = False) -> PipelineResult:
    """Ejecuta el pipeline simplificado unificado.

    Args:
        year: Año objetivo del cálculo. Por defecto, el año actual.
        month: Mes objetivo (1-12). Por defecto, el mes actual.
        use_test_odoo: Si usar entorno de test para Odoo.

    Returns:
        PipelineResult con contadores y estadísticas de upserts.
    """
    # 1) Obtener datos de ventas y preparar forecaster
    logger.info("Iniciando pipeline unificado de forecasting", year=year, month=month, use_test_odoo=use_test_odoo)

    forecaster = SalesForecaster()

    # 2) Generar forecasts para todos los SKUs
    t0 = time.monotonic()
    logger.info("[1] Generando forecasts de ventas para todos los SKUs")
    all_forecasts = forecaster.run_forecasting_for_all_skus()
    # Sanitizar claves de SKU para evitar valores inválidos como 'false'
    original_count = len(all_forecasts) if all_forecasts else 0
    all_forecasts = _sanitize_forecast_keys(all_forecasts or {})
    cleaned_count = len(all_forecasts)
    logger.info(
        "[1] Forecasting completado",
        duration_seconds=round(time.monotonic() - t0, 1),
        total_skus=cleaned_count,
        removed_invalid_skus=max(original_count - cleaned_count, 0)
    )
    if not all_forecasts:
        raise RuntimeError("No se pudieron generar forecasts de ventas")

    # Determinar periodo objetivo
    if year is None or month is None:
        current = pd.Timestamp.today()
        year = int(year or current.year)
        month = int(month or current.month)

    # 3) Extraer forecasts para el mes objetivo
    t1 = time.monotonic()
    logger.info("[2] Extrayendo forecast mensual objetivo", target_year=year, target_month=month)
    monthly_forecasts = _extract_monthly_forecast(all_forecasts, year, month)
    if not monthly_forecasts:
        raise RuntimeError(f"No hay forecasts para {month}/{year} en las series generadas")
    logger.info("[2] Forecast mensual extraído", skus_with_value=len(monthly_forecasts), duration_seconds=round(time.monotonic() - t1, 1))

    # 4) Obtener inventario desde Odoo
    skus_for_month = list(monthly_forecasts.keys())
    t2 = time.monotonic()
    logger.info("[3] Obteniendo inventario desde Odoo", total_skus=len(skus_for_month))
    inventory_data = get_inventory_from_odoo(skus_for_month, use_test_odoo=use_test_odoo)
    logger.info("[3] Inventario obtenido", duration_seconds=round(time.monotonic() - t2, 1), skus_found=sum(1 for v in inventory_data.values() if v.get('found')))

    # 5) Obtener máximos de ventas históricas
    t3 = time.monotonic()
    logger.info("[4] Obteniendo máximos de ventas históricas")
    max_sales_data = forecaster.get_max_monthly_sales_for_skus(skus_for_month)
    logger.info("[4] Máximos históricos obtenidos", duration_seconds=round(time.monotonic() - t3, 1))

    # 6) Obtener precios unitarios
    t4 = time.monotonic()
    logger.info("[5] Obteniendo precios unitarios")
    unit_prices_data = forecaster.get_unit_prices_for_skus(skus_for_month)
    logger.info("[5] Precios unitarios obtenidos", duration_seconds=round(time.monotonic() - t4, 1))

    # 7) Construir DataFrame unificado
    t5 = time.monotonic()
    logger.info("[6] Construyendo DataFrame unificado")
    unified_df = _build_unified_forecast_df(monthly_forecasts, inventory_data, max_sales_data, unit_prices_data, year, month)
    logger.info("[6] DataFrame unificado construido", rows=len(unified_df), duration_seconds=round(time.monotonic() - t5, 1))

    # 8) Upsert a tabla forecast unificada
    t6 = time.monotonic()
    logger.info("[7] Iniciando upsert en tabla forecast unificada", total_rows=len(unified_df))
    forecast_db_updater = DatabaseForecastUpdater()
    forecast_upsert_stats = forecast_db_updater.upsert_unified_forecasts(unified_df)
    logger.info("[7] Upsert unificado completado", duration_seconds=round(time.monotonic() - t6, 1), **forecast_upsert_stats)

    return PipelineResult(
        year=year,
        month=month,
        total_skus_forecasted=len(all_forecasts),
        total_records_upserted=int(forecast_upsert_stats.get('total_processed', 0)),
        forecast_upsert_stats=forecast_upsert_stats,
    )


def main():
    """Función principal para ejecutar el pipeline desde línea de comandos."""
    try:
        result = run_pipeline()
        print(
            f"Pipeline unificado completado para {result.month:02d}/{result.year} | "
            f"Registros procesados: {result.total_records_upserted:,}"
        )
        return 0
    except Exception as e:
        print(f"Error ejecutando pipeline: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
