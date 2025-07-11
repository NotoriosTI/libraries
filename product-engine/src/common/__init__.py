"""
Common Module

Módulo con configuración, utilidades y componentes compartidos entre db_manager y db_client.
"""

from common.config import ProductEngineConfig, config
from common.embedding_generator import EmbeddingGenerator
from common.models import ProductData, SearchResult
from common.database import DatabaseConnection, database

__all__ = [
    "ProductEngineConfig",
    "config",
    "EmbeddingGenerator", 
    "ProductData",
    "SearchResult",
    "DatabaseConnection",
    "database"
] 