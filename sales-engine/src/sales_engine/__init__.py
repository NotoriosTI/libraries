"""
Sales Engine Package - Refactored Database synchronization for Odoo to PostgreSQL

This refactored version includes:
- Proper upsert logic with composite primary key (salesinvoiceid, items_product_sku)
- Timestamp-based incremental sync using updated_at column
- Robust error handling and connection pooling
- Follows product-engine architecture patterns
- Shared Cloud SQL proxy integration

Key Components:
- DatabaseUpdater: Main sync orchestrator with upsert logic
- SalesDataProvider: Odoo integration layer
- UpdateResult: Comprehensive sync result tracking

Author: Bastian Ibañez (Refactored)
"""

# Package version
__version__ = "1.0.0-refactored"

# Main exports from refactored modules
from .db_updater import DatabaseUpdater, UpdateResult
from .sales_integration import SalesDataProvider, read_sales_by_date_range

__all__ = [
    "DatabaseUpdater",
    "UpdateResult", 
    "SalesDataProvider",
    "read_sales_by_date_range",
    "__version__"
]

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
    return DatabaseUpdater(*args, **kwargs)