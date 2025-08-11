"""
Sales Engine Database Client Module

Módulo simplificado para leer datos de la base de datos de ventas.
"""

from sales_engine.db_client.db_reader import DatabaseReader
from .query_builder import QueryBuilder
from .forecast_reader import ForecastReader, get_forecasts_by_month
from .production_forecast_reader import ProductionForecastReader, get_production_forecasts_by_month

__all__ = ['DatabaseReader', 'QueryBuilder', 'ForecastReader', 'get_forecasts_by_month', 'ProductionForecastReader', 'get_production_forecasts_by_month'] 