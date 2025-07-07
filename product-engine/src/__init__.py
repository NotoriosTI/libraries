# Este archivo permite que el directorio product-engine sea tratado como un paquete Python. 
# Re-exporta las funciones principales del paquete product_engine para mantener compatibilidad

from product_engine import (
    search_products,
    get_product_by_sku,
    get_products_count,
    ProductSearchClient,
    ProductReader,
    SyncManager,
    ProductUpdater,
    ProductData,
    SearchResult,
    EmbeddingGenerator,
    config,
    database
)

__all__ = [
    "search_products",
    "get_product_by_sku", 
    "get_products_count",
    "ProductSearchClient",
    "ProductReader",
    "SyncManager",
    "ProductUpdater",
    "ProductData",
    "SearchResult",
    "EmbeddingGenerator",
    "config",
    "database"
] 
