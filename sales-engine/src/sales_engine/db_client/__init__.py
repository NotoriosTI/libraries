"""
Sales Engine Database Client Module

Módulo simplificado para leer datos de la base de datos de ventas.
"""

from sales_engine.db_client.db_reader import DatabaseReader
from .query_builder import QueryBuilder

__all__ = ['DatabaseReader', 'QueryBuilder'] 