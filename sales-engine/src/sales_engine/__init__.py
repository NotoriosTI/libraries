"""
Sales Engine Package - Refactored Database synchronization for Odoo to PostgreSQL

This refactored version includes:
- Proper upsert logic with composite primary key (salesinvoiceid, items_product_sku)
- Timestamp-based incremental sync using updated_at column
- Robust error handling and connection pooling
- Follows product-engine architecture patterns
- Shared Cloud SQL proxy integration
- Database client module for reading data

Key Components:
- DatabaseUpdater: Main sync orchestrator with upsert logic
- SalesDataProvider: Odoo integration layer
- UpdateResult: Comprehensive sync result tracking
- DatabaseReader: Client for reading sales data
- QueryBuilder: Dynamic SQL query builder

Author: Bastian Ibañez (Refactored)
"""

# Package version
__version__ = "1.0.0-refactored"

# NOTE: Imports commented to avoid RuntimeWarning when executing modules directly
# Use main.py as entry point or import explicitly when needed
# from .db_updater import DatabaseUpdater, UpdateResult
# from .db_client import DatabaseReader, QueryBuilder

__all__ = [
    # "DatabaseUpdater",
    # "UpdateResult",
    # "DatabaseReader", 
    # "QueryBuilder",
    "__version__"
]

# Lazy import functions to avoid loading heavy modules
def get_database_updater(*args, **kwargs):
    """
    Get DatabaseUpdater instance with lazy loading.
    
    This avoids importing the module until actually needed,
    preventing RuntimeWarnings when executing modules directly.
    """
    from .db_updater import DatabaseUpdater
    return DatabaseUpdater(*args, **kwargs)


def get_database_reader(*args, **kwargs):
    """
    Get DatabaseReader instance with lazy loading.
    
    This avoids importing the module until actually needed,
    preventing RuntimeWarnings when executing modules directly.
    """
    from .db_client import DatabaseReader
    return DatabaseReader(*args, **kwargs)


def get_query_builder(*args, **kwargs):
    """
    Get QueryBuilder instance with lazy loading.
    
    This avoids importing the module until actually needed,
    preventing RuntimeWarnings when executing modules directly.
    """
    from .db_client import QueryBuilder
    return QueryBuilder(*args, **kwargs)

# Backward compatibility note
def get_legacy_updater(*args, **kwargs):
    """
    Legacy compatibility function.
    
    Note: The refactored DatabaseUpdater now uses:
    - Composite primary key upserts
    - Timestamp-based incremental sync
    - Proper error handling and connection pooling
    
    All existing functionality is preserved but enhanced.
    """
    return get_database_updater(*args, **kwargs)