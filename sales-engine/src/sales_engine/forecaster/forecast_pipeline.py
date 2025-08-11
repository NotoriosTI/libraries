"""
Pipeline unificado de forecasting y producción

Flujo:
1) Obtener datos de ventas (tabla sales_items)
2) Calcular forecasts de ventas por SKU
3) Calcular production forecast (Forecast - Inventario Odoo) usando los forecasts en memoria
4) Upsert a tabla forecast
5) Upsert a tabla production_forecast

Este módulo reutiliza la lógica existente para forecasting y persistencia, pero
evita dependencias innecesarias entre pasos leyendo y usando los forecasts en memoria
para el cálculo de producción antes de persistirlos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any, List
import time

import pandas as pd

from .sales_forcaster import SalesForecaster
from .generate_all_forecasts import (
    convert_to_dataframe,
    add_summary_statistics,
    DatabaseForecastUpdater,
)
from .production_forecast_updater import (
    ProductionForecastUpdater,
    get_inventory_from_odoo,
    IGNORE_SKU,
)
from config_manager import secrets

# Logger consistente con el resto del proyecto
from dev_utils import PrettyLogger
logger = PrettyLogger("forecast-pipeline")

@dataclass
class PipelineResult:
    year: int
    month: int
    total_skus_forecasted: int
    total_forecast_records_upserted: int
    total_production_records_upserted: int
    forecast_upsert_stats: Dict[str, Any]
    production_upsert_stats: Dict[str, Any]


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


def _build_production_df(
    monthly_forecasts: Dict[str, int],
    inventory_data: Dict[str, Dict],
) -> pd.DataFrame:
    """Construye el DataFrame requerido por ProductionForecastUpdater.upsert_production_data()."""
    # Normalizar claves de SKUs a string para evitar desalineación (int vs str)
    monthly_forecasts_normalized: Dict[str, int] = {str(sku): qty for sku, qty in monthly_forecasts.items()}

    # Aplicar filtro de SKUs ignorados
    ignore_skus_str = {str(s) for s in IGNORE_SKU} if IGNORE_SKU else set()
    valid_skus = [sku for sku in monthly_forecasts_normalized.keys() if sku not in ignore_skus_str]

    # Heurística de prioridad: propuesta práctica
    # - Si forecast >= 60: usar porcentaje (35% y 15%)
    # - Si forecast < 60: usar umbrales fijos (40 y 15)
    DECISION_FORECAST_THRESHOLD = 60
    PCT_HIGH = 0.35
    PCT_MED = 0.15
    FIXED_HIGH = 40
    FIXED_MED = 15

    rows: List[Dict[str, Any]] = []
    for sku in valid_skus:
        forecast_qty = float(monthly_forecasts_normalized.get(sku, 0))

        # inventory_data debe tener claves string
        inv_info = inventory_data.get(sku, {})
        if inv_info.get('found', False):
            inventory_qty = float(inv_info.get('qty_available', 0) or 0)
            product_name = inv_info.get('product_name', 'Sin nombre')
        else:
            # Excluir explícitamente productos no encontrados en Odoo (alineado al updater)
            continue

        production_gap = forecast_qty - inventory_qty
        # Normalizar: need >= 0 y exceso separado
        production_needed = production_gap if production_gap > 0 else 0.0
        product_excess = -production_gap if production_gap < 0 else 0.0

        # Calcular prioridad
        if forecast_qty >= DECISION_FORECAST_THRESHOLD and forecast_qty > 0:
            shortfall_pct = production_needed / forecast_qty
            if shortfall_pct >= PCT_HIGH:
                priority = 'ALTA'
            elif shortfall_pct >= PCT_MED:
                priority = 'MEDIA'
            else:
                priority = 'BAJA'
        else:
            if production_needed >= FIXED_HIGH:
                priority = 'ALTA'
            elif production_needed >= FIXED_MED:
                priority = 'MEDIA'
            else:
                priority = 'BAJA'

        rows.append({
            'sku': sku,
            'product_name': product_name,
            'forecast_quantity': forecast_qty,
            'inventory_available': inventory_qty,
            'production_needed': production_needed,
            'product_excess': product_excess,
            'priority': priority,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('production_needed', ascending=False).reset_index(drop=True)
    return df


def run_pipeline(year: Optional[int] = None, month: Optional[int] = None, use_test_odoo: bool = False) -> PipelineResult:
    """Ejecuta el pipeline completo y persiste ambos resultados en base de datos.

    Args:
        year: Año objetivo del cálculo. Por defecto, el año actual.
        month: Mes objetivo (1-12). Por defecto, el mes actual.
        use_test_odoo: Si usar entorno de test para Odoo.

    Returns:
        PipelineResult con contadores y estadísticas de upserts.
    """
    # 1) Obtener datos de ventas y preparar forecaster
    logger.info("Iniciando pipeline de forecasting y producción", year=year, month=month, use_test_odoo=use_test_odoo)

    forecaster = SalesForecaster()

    # Reutilizamos el método de alto nivel para robustez (internamente hace 1 y 2)
    t0 = time.monotonic()
    logger.info("[1-2] Generando forecasts de ventas para todos los SKUs (esto puede tardar varios minutos)")
    all_forecasts = forecaster.run_forecasting_for_all_skus()
    # Sanitizar claves de SKU para evitar valores inválidos como 'false'
    original_count = len(all_forecasts) if all_forecasts else 0
    all_forecasts = _sanitize_forecast_keys(all_forecasts or {})
    cleaned_count = len(all_forecasts)
    logger.info(
        "[1-2] Forecasting completado",
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

    # 2) Forecast de ventas ya calculado (all_forecasts)
    # 3) Calcular production forecast a partir de forecasts EN MEMORIA
    t1 = time.monotonic()
    logger.info("[3] Extrayendo forecast mensual objetivo desde series en memoria", target_year=year, target_month=month)
    monthly_forecasts = _extract_monthly_forecast(all_forecasts, year, month)
    if not monthly_forecasts:
        raise RuntimeError(f"No hay forecasts para {month}/{year} en las series generadas")
    logger.info("[3] Forecast mensual extraído", skus_with_value=len(monthly_forecasts), duration_seconds=round(time.monotonic() - t1, 1))

    # Inventario desde Odoo para los SKUs con forecast en el mes objetivo
    skus_for_month = list(monthly_forecasts.keys())
    t2 = time.monotonic()
    logger.info("[3] Obteniendo inventario desde Odoo", total_skus=len(skus_for_month))
    inventory_data = get_inventory_from_odoo(skus_for_month, use_test_odoo=use_test_odoo)
    logger.info("[3] Inventario obtenido", duration_seconds=round(time.monotonic() - t2, 1), skus_found=sum(1 for v in inventory_data.values() if v.get('found')))

    # Construir DataFrame de producción (alineado al updater)
    t3 = time.monotonic()
    production_df = _build_production_df(monthly_forecasts, inventory_data)
    logger.info("[3] DataFrame de producción construido", rows=len(production_df), duration_seconds=round(time.monotonic() - t3, 1))

    # 4) Upsert a tabla forecast (todos los horizontes)
    t4 = time.monotonic()
    logger.info("[4] Preparando DataFrame de forecasts para upsert (todas las fechas)")
    df_forecast = convert_to_dataframe(all_forecasts)
    logger.info("[4] Calculando estadísticas por SKU para forecasts", rows=len(df_forecast))
    df_with_stats, _sku_stats = add_summary_statistics(df_forecast)

    # Opción A: Forzar la presencia del mes objetivo en la tabla forecast
    # Construimos filas mínimas para (year, month) con los valores de monthly_forecasts
    # y las fusionamos con df_with_stats antes del upsert.
    try:
        logger.info("[4] Asegurando fila de forecast para el mes objetivo", target_year=year, target_month=month)
        # Fecha fin de mes
        target_date = pd.Period(freq='M', year=year, month=month).to_timestamp('M')
        month_name = target_date.strftime('%B')
        quarter = f"Q{((month-1)//3)+1}"
        week_of_year = target_date.isocalendar()[1]

        forced_rows = []
        for sku, qty in monthly_forecasts.items():
            forced_rows.append({
                'sku': sku,
                'forecast_date': target_date,
                'forecasted_quantity': int(qty),
                'year': int(year),
                'month': int(month),
                'month_name': month_name,
                'quarter': quarter,
                'week_of_year': int(week_of_year),
                # Estadísticas opcionales (NULL en DB si None)
                'total_forecast_12_months': None,
                'avg_monthly_forecast': None,
                'std_dev': None,
                'min_monthly_forecast': None,
                'max_monthly_forecast': None,
                'months_forecasted': None,
            })

        if forced_rows:
            df_forced = pd.DataFrame(forced_rows)
            # Evitar duplicados por clave (sku, forecast_date)
            # Filtrar entradas vacías antes de concatenar para evitar warnings
            df_with_stats_clean = df_with_stats.dropna(how='all')
            df_forced_clean = df_forced.dropna(how='all')
            
            # Excluir DataFrames vacíos o totalmente NA para evitar FutureWarning
            frames = []
            for _df in (df_with_stats_clean, df_forced_clean):
                if not _df.empty and not _df.isna().all().all():
                    frames.append(_df)
            
            if frames:
                combined = pd.concat(frames, ignore_index=True)
            else:
                combined = pd.DataFrame()
            
            if not combined.empty:
                combined = combined.sort_values(['sku', 'forecast_date']).drop_duplicates(subset=['sku', 'forecast_date'], keep='last')
                df_with_stats = combined.reset_index(drop=True)
                logger.info("[4] Fila de mes objetivo asegurada en forecast", total_rows=len(df_with_stats))
            else:
                logger.warning("[4] No se pudo combinar DataFrames - ambos están vacíos")
        else:
            logger.info("[4] No hay filas para forzar en mes objetivo (monthly_forecasts vacío)")
    except Exception as e:
        logger.warning("[4] No se pudo forzar el mes objetivo en forecast", error=str(e))
    logger.info("[4] Iniciando upsert de forecasts en base de datos", total_rows=len(df_with_stats))
    forecast_db_updater = DatabaseForecastUpdater()
    forecast_upsert_stats = forecast_db_updater.upsert_forecasts(df_with_stats)
    logger.info("[4] Upsert de forecasts completado", duration_seconds=round(time.monotonic() - t4, 1), **forecast_upsert_stats)

    # 5) Upsert a tabla production_forecast (solo mes objetivo)
    t5 = time.monotonic()
    logger.info("[5] Iniciando upsert de production_forecast en base de datos", total_rows=len(production_df), year=year, month=month)
    prod_updater = ProductionForecastUpdater()
    production_upsert_stats = prod_updater.upsert_production_data(production_df, year=year, month=month)
    logger.info("[5] Upsert de production_forecast completado", duration_seconds=round(time.monotonic() - t5, 1), **production_upsert_stats)

    return PipelineResult(
        year=year,
        month=month,
        total_skus_forecasted=len(all_forecasts),
        total_forecast_records_upserted=int(forecast_upsert_stats.get('total_processed', 0)),
        total_production_records_upserted=int(production_upsert_stats.get('total_processed', 0)),
        forecast_upsert_stats=forecast_upsert_stats,
        production_upsert_stats=production_upsert_stats,
    )


if __name__ == "__main__":
    result = run_pipeline()
    print(
        f"✅ Pipeline completado para {result.month:02d}/{result.year} | "
        f"Forecast upserts: {result.total_forecast_records_upserted:,} | "
        f"Production upserts: {result.total_production_records_upserted:,}"
    )
