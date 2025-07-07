"""
Product Engine - Product catalog synchronization and search system.

This package provides a complete solution for synchronizing products from Odoo
to PostgreSQL with OpenAI embeddings and hybrid search capabilities.

New Modular Architecture:
- src/common/: Shared configuration, models, and utilities
- src/db_manager/: Database write operations (sync, updates)
- src/db_client/: Database read operations (search, queries)

Main Components:
- SyncManager: Orchestrates full synchronization from Odoo
- ProductSearchClient: Hybrid search (SKU + semantic)
- ProductReader: Basic read operations
- ProductUpdater: Database write operations
"""
from typing import List, Dict, Any, Optional

# Import the new modular structure 
from db_client.product_search import ProductSearchClient
from db_client.product_reader import ProductReader
from db_manager.sync_manager import SyncManager
from db_manager.product_updater import ProductUpdater

# Import common components
from common.config import config
from common.models import ProductData, SearchResult
from common.embedding_generator import EmbeddingGenerator
from common.database import database

# Create global instances for convenience
_search_client = None
_product_reader = None


def get_search_client() -> ProductSearchClient:
    """Get a shared instance of ProductSearchClient."""
    global _search_client
    if _search_client is None:
        _search_client = ProductSearchClient()
    return _search_client


def get_product_reader() -> ProductReader:
    """Get a shared instance of ProductReader."""
    global _product_reader
    if _product_reader is None:
        _product_reader = ProductReader()
    return _product_reader


def search_products(query: str, limit: int = 20, 
                   similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Search products using hybrid approach: exact SKU + semantic embedding search.
    
    This is the main public API function for searching products. It provides
    a simple interface while using the modular architecture underneath.
    
    Args:
        query: Search query (can be SKU or product name/description)
        limit: Maximum number of results to return
        similarity_threshold: Minimum similarity score for semantic search (0.0-1.0)
        
    Returns:
        List of product dictionaries ranked by relevance
        
    Example:
        >>> results = search_products("ACO-100")  # Exact SKU search
        >>> results = search_products("aceite de coco")  # Semantic search
        >>> for product in results:
        ...     print(f"{product['sku']}: {product['name']}")
    """
    try:
        search_client = get_search_client()
        search_results = search_client.search_products(
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        
        # Convert SearchResult objects to dictionaries for backward compatibility
        return [result.to_dict() for result in search_results]
        
    except Exception as e:
        # Import logger locally to avoid circular imports
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("Search products failed", error=str(e), query=query)
        return []


def get_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """
    Get a single product by SKU.
    
    Args:
        sku: Product SKU to retrieve
        
    Returns:
        Product dictionary if found, None otherwise
    """
    try:
        reader = get_product_reader()
        product = reader.get_product_by_sku(sku)
        return product.to_dict() if product else None
        
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("Get product by SKU failed", error=str(e), sku=sku)
        return None


def get_products_count(active_only: bool = True) -> int:
    """
    Get total count of products.
    
    Args:
        active_only: If True, only count active products
        
    Returns:
        Number of products
    """
    try:
        reader = get_product_reader()
        return reader.get_products_count(active_only=active_only)
        
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("Get products count failed", error=str(e))
        return 0


# Backward compatibility - export the main classes
__all__ = [
    # Main search function (backward compatibility)
    "search_products",
    "get_product_by_sku", 
    "get_products_count",
    
    # New modular components
    "SyncManager",
    "ProductSearchClient",
    "ProductReader", 
    "ProductUpdater",
    
    # Common components
    "ProductData",
    "SearchResult",
    "EmbeddingGenerator",
    "config",
    "database",
    
    # Convenience functions
    "get_search_client",
    "get_product_reader"
]
