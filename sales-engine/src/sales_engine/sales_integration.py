"""
Sales Integration Module

This module acts as an adapter between the `odoo-api` package and the
`DatabaseUpdater`. It is responsible for fetching sales data from Odoo,
mapping the data to the required database schema, and providing a clean
interface for the rest of the application.

Author: Bastian Ibañez
"""

# Standard library imports
from datetime import date
from typing import Optional, Tuple, Dict, Any

# Third-party imports
import pandas as pd
import structlog

# Local imports
from odoo_api.sales import OdooSales
from .config import get_odoo_config

# --- Module-level logger ---
logger = structlog.get_logger(__name__)


class SalesDataProvider:
    """
    Sales data provider that integrates with the odoo-api package.
    Provides a clean interface for DatabaseUpdater to retrieve sales data.
    """

    def __init__(self, use_test: bool = False):
        """
        Initialize with a shared config manager.

        Args:
            use_test: Whether to use the test Odoo configuration.
        """
        self.config = get_odoo_config(use_test=use_test)
        self._odoo_sales: Optional[OdooSales] = None
        self.use_test = use_test
        self.logger = logger.bind(odoo_env='test' if use_test else 'production')
        self.logger.info("SalesDataProvider initialized.")

    def _get_odoo_sales(self) -> OdooSales:
        """Get or create OdooSales instance (lazy initialization)."""
        if self._odoo_sales is None:
            self.logger.info("Creating new OdooSales instance...")
            try:
                self._odoo_sales = OdooSales(
                    url=self.config['url'],
                    db=self.config['db'],
                    username=self.config['username'],
                    password=self.config['password']
                )
                self.logger.info("OdooSales instance created successfully.")
            except Exception as e:
                self.logger.error("Failed to initialize OdooSales", error=str(e), exc_info=True)
                raise RuntimeError("Failed to initialize OdooSales.") from e
        return self._odoo_sales

    def read_sales_by_date_range(
        self,
        start_date: date,
        end_date: date,
        limit: Optional[int] = None,
        include_lines: bool = True,
        batch_size: int = 500
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Read sales data for a date range with proper column mapping.
        """
        self.logger.info(
            "Requesting sales data by date range",
            start_date=str(start_date),
            end_date=str(end_date),
            limit=limit
        )
        try:
            odoo_sales = self._get_odoo_sales()
            result = odoo_sales.read_sales_by_date_range(
                start_date=start_date, end_date=end_date, limit=limit,
                include_lines=include_lines, batch_size=batch_size
            )

            if not isinstance(result, dict) or 'orders' not in result or 'lines' not in result:
                raise RuntimeError("Invalid response format from OdooSales")

            orders_df = self._map_orders_columns(result['orders'])
            lines_df = self._map_lines_columns(result['lines'])

            self.logger.info(
                "Sales data retrieved and mapped",
                order_count=len(orders_df),
                line_count=len(lines_df)
            )
            return orders_df, lines_df
        except Exception as e:
            self.logger.error("Failed to retrieve sales data by date range", error=str(e), exc_info=True)
            raise

    def _map_orders_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map orders DataFrame columns to the DatabaseUpdater schema."""
        if df.empty:
            return df

        column_mapping = {
            'id': 'order_id', 'name': 'salesInvoiceId', 'date_order': 'issuedDate',
            'partner_name': 'customer_name', 'partner_id': 'customer_customerid',
            'partner_vat': 'customer_vatid', 'salesperson_name': 'salesman_name',
            'payment_term_name': 'term_name', 'warehouse_name': 'warehouse_name',
            'amount_untaxed': 'totals_net', 'amount_tax': 'totals_vat',
            'amount_total': 'total_total', 'sales_channel': 'sales_channel',
        }
        df = df.rename(columns=column_mapping, errors='ignore')

        # Ensure order_id and salesInvoiceId are consistent types
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(int)
        
        # Fix: Ensure salesInvoiceId is string type (use name, not id)
        if 'salesInvoiceId' not in df.columns and 'name' in df.columns:
            df['salesInvoiceId'] = df['name'].astype(str)
        elif 'salesInvoiceId' in df.columns:
            df['salesInvoiceId'] = df['salesInvoiceId'].astype(str)

        required_columns = {
            'order_id': 0, 'doctype_name': 'Factura', 'docnumber': df.get('salesInvoiceId', ''),
            'customer_customerid': 0, 'customer_name': '', 'customer_vatid': '',
            'salesman_name': '', 'term_name': '', 'warehouse_name': '',
            'totals_net': 0.0, 'totals_vat': 0.0,
            'issuedDate': None, 'sales_channel': ''
        }
        for col, default in required_columns.items():
            if col not in df.columns:
                df[col] = default
        return df

    def _map_lines_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map lines DataFrame columns to the DatabaseUpdater schema."""
        if df.empty:
            return df

        column_mapping = {
            'order_id': 'order_id',
            'product_sku': 'items_product_sku',
            'product_name': 'items_product_description', 'qty': 'items_quantity',
            'price_unit': 'items_unitPrice',
        }
        df = df.rename(columns=column_mapping, errors='ignore')
        
        # Ensure order_id is consistent type
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(int)
        
        required_columns = {
            'order_id': 0, 'items_product_description': '', 'items_product_sku': '',
            'items_quantity': 0.0, 'items_unitPrice': 0.0
        }
        for col, default in required_columns.items():
            if col not in df.columns:
                df[col] = default
        return df

    def read_sales_by_day(self, day: date) -> pd.DataFrame:
        """Read sales data for a specific day."""
        self.logger.info("Requesting sales data by day", day=str(day))
        try:
            odoo_sales = self._get_odoo_sales()
            return odoo_sales.read_sales_by_day(day)
        except Exception as e:
            self.logger.error("Failed to retrieve sales data by day", day=str(day), error=str(e), exc_info=True)
            raise

    def close(self):
        """Clean up resources."""
        if self._odoo_sales and hasattr(self._odoo_sales, 'close'):
            self._odoo_sales.close()
        self._odoo_sales = None
        self.logger.info("SalesDataProvider closed.")


# --- Module-level Singleton for Backward Compatibility ---
_default_provider: Optional[SalesDataProvider] = None
_provider_config: Dict[str, Any] = {"use_test": None}

def get_sales_provider(use_test: bool = False) -> SalesDataProvider:
    """Get or create the singleton SalesDataProvider instance."""
    global _default_provider, _provider_config
    
    # If a provider exists but the config has changed, reset it
    if _default_provider and _provider_config["use_test"] != use_test:
        logger.info("Odoo environment changed, resetting provider.", old_env=_provider_config["use_test"], new_env=use_test)
        _default_provider.close()
        _default_provider = None

    if _default_provider is None:
        _default_provider = SalesDataProvider(use_test=use_test)
        _provider_config["use_test"] = use_test
        
    return _default_provider

def read_sales_by_date_range(
    start_date: date, end_date: date, limit: Optional[int] = None,
    include_lines: bool = True, batch_size: int = 500, use_test: bool = False
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Module-level function for DatabaseUpdater compatibility."""
    provider = get_sales_provider(use_test=use_test)
    return provider.read_sales_by_date_range(start_date, end_date, limit, include_lines, batch_size)

def read_sales_by_day(day: date, use_test: bool = False) -> pd.DataFrame:
    """Module-level function for reading sales by day."""
    provider = get_sales_provider(use_test=use_test)
    return provider.read_sales_by_day(day)

def cleanup_sales_provider():
    """Clean up the module-level provider instance."""
    global _default_provider
    if _default_provider:
        _default_provider.close()
        _default_provider = None
