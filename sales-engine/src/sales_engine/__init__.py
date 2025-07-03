"""
Sales Engine Package - Database synchronization for Odoo to PostgreSQL
"""

# Package version
__version__ = "0.1.0"

# Main exports
from .db_updater import DatabaseUpdater, UpdateResult
from .sales_integration import SalesDataProvider, read_sales_by_date_range

__all__ = [
    "DatabaseUpdater",
    "UpdateResult", 
    "SalesDataProvider",
    "read_sales_by_date_range",
    "__version__"
]
