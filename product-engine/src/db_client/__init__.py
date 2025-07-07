"""
DB Client Module

Módulo responsable de las operaciones de lectura de la base de datos.
Incluye búsqueda híbrida, consultas de productos y APIs para dependencias externas.
"""

from db_client.product_search import ProductSearchClient
from db_client.product_reader import ProductReader

__all__ = [
    "ProductSearchClient", 
    "ProductReader"
] 