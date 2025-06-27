"""
Sales integration module - Updated to use config-manager.
"""

# Standard library imports
from datetime import date
from typing import Optional, Tuple

# Third-party imports
from odoo_api.sales import OdooSales
import pandas as pd
# Local imports
from .config import get_odoo_config

# Simple logging setup for now
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SalesDataProvider:
    """
    Sales data provider that integrates with the odoo-api package.
    Provides a clean interface for DatabaseUpdater to retrieve sales data.
    """
    
    def __init__(self, use_test: bool = False):
        """
        Initialize with shared config manager.
        
        Args:
            use_test: Whether to use test Odoo configuration
        """
        config = get_odoo_config(use_test=use_test)
        self._odoo_sales: Optional[OdooSales] = None
        self.config = config
        self.use_test = use_test
        
        logger.info(f"SalesDataProvider initialized for {'test' if use_test else 'production'} environment")
    
    def _get_odoo_sales(self) -> OdooSales:
        """Get or create OdooSales instance (lazy initialization)."""
        if self._odoo_sales is None:
            try:
                self._odoo_sales = OdooSales(
                    url=self.config['url'],
                    db=self.config['db'],
                    username=self.config['username'],
                    password=self.config['password']
                )
                logger.info("OdooSales instance created successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OdooSales: {e}")
                raise RuntimeError(f"Failed to initialize OdooSales: {e}")
        
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
        
        Args:
            start_date: Start date for the range
            end_date: End date for the range  
            limit: Maximum number of orders to retrieve
            include_lines: Whether to include product lines
            batch_size: Batch size for line processing
            
        Returns:
            Tuple: (orders_df, lines_df) with columns mapped for DatabaseUpdater
        """
        logger.info(
            f"Retrieving sales data from {start_date} to {end_date}, "
            f"limit={limit}, include_lines={include_lines}"
        )
        
        try:
            odoo_sales = self._get_odoo_sales()
            result = odoo_sales.read_sales_by_date_range(
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                include_lines=include_lines,
                batch_size=batch_size
            )
            
            if isinstance(result, str):
                raise RuntimeError(f"Error retrieving sales data: {result}")
            
            if not isinstance(result, dict) or 'orders' not in result or 'lines' not in result:
                raise RuntimeError("Invalid response format from OdooSales")
            
            orders_df = result['orders']
            lines_df = result['lines']
            
            # Map columns to match DatabaseUpdater expectations
            orders_df = self._map_orders_columns(orders_df)
            lines_df = self._map_lines_columns(lines_df)
            
            logger.info(
                f"Sales data retrieved successfully: {len(orders_df)} orders, {len(lines_df)} lines"
            )
            
            return orders_df, lines_df
            
        except Exception as e:
            logger.error(f"Failed to retrieve sales data: {e}")
            raise
    
    def _map_orders_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map orders DataFrame columns to DatabaseUpdater schema."""
        if df.empty:
            return df
        
        logger.debug("Mapping orders columns to DatabaseUpdater schema")
        
        # Column mapping from odoo-api output to sales_items schema
        column_mapping = {
            'name': 'salesInvoiceId',           # Order name -> invoice ID
            'date_order': 'issuedDate',         # Order date -> issued date
            'partner_name': 'customer_name',    # Partner name -> customer name
            'partner_id': 'customer_customerid', # Partner ID -> customer ID  
            'partner_vat': 'customer_vatid',    # Partner VAT -> customer VAT ID
            'salesperson_name': 'salesman_name', # Salesperson -> salesman
            'payment_term_name': 'term_name',   # Payment terms
            'warehouse_name': 'warehouse_name', # Warehouse
            'amount_untaxed': 'totals_net',     # Net amount
            'amount_tax': 'totals_vat',         # Tax amount
            'amount_total': 'total_total',      # Total amount
            'sales_channel': 'sales_channel',   # Sales channel
        }
        
        # Apply column mapping
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and old_col != new_col:
                df[new_col] = df[old_col]
        
        # Add missing required columns with defaults
        required_columns = {
            'salesInvoiceId': df.get('name', ''),
            'doctype_name': 'Factura',
            'docnumber': df.get('salesInvoiceId', df.get('name', '')),
            'customer_customerid': 0,
            'customer_name': '',
            'customer_vatid': '',
            'salesman_name': '',
            'term_name': '',
            'warehouse_name': '',
            'totals_net': 0.0,
            'totals_vat': 0.0,
            'total_total': 0.0,
            'issuedDate': None,
            'sales_channel': ''
        }
        
        for col, default_value in required_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        return df
    
    def _map_lines_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map lines DataFrame columns to DatabaseUpdater schema."""
        if df.empty:
            return df
        
        logger.debug("Mapping lines columns to DatabaseUpdater schema")
        
        # Column mapping for lines
        line_column_mapping = {
            'sale_order': 'salesInvoiceId',          # Sale order -> invoice ID
            'product_sku': 'items_product_sku',      # Product SKU
            'product_name': 'items_product_description', # Product description
            'qty': 'items_quantity',                 # Quantity
            'price_unit': 'items_unitPrice',         # Unit price
        }
        
        # Apply line column mapping
        for old_col, new_col in line_column_mapping.items():
            if old_col in df.columns and old_col != new_col:
                df[new_col] = df[old_col]
        
        # Ensure required line columns exist
        required_line_columns = {
            'salesInvoiceId': '',
            'items_product_description': '',
            'items_product_sku': '',
            'items_quantity': 0.0,
            'items_unitPrice': 0.0
        }
        
        for col, default_value in required_line_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        return df
    
    def read_sales_by_day(self, day: date) -> pd.DataFrame:
        """
        Read sales data for a specific day.
        
        Args:
            day: Date to retrieve sales for
            
        Returns:
            DataFrame: Sales data for the specified day
        """
        logger.info(f"Retrieving sales data for day: {day}")
        
        try:
            odoo_sales = self._get_odoo_sales()
            result = odoo_sales.read_sales_by_day(day)
            
            if isinstance(result, str):
                raise RuntimeError(f"Error retrieving sales data for day {day}: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve sales data for day {day}: {e}")
            raise
    
    def close(self):
        """Clean up resources."""
        if self._odoo_sales is not None:
            # Close any connections if the OdooSales class supports it
            if hasattr(self._odoo_sales, 'close'):
                self._odoo_sales.close()
            self._odoo_sales = None
            logger.info("Sales data provider closed")

# Module-level functions for backward compatibility with DatabaseUpdater
_default_provider: Optional[SalesDataProvider] = None

def get_sales_provider(use_test: bool = False) -> SalesDataProvider:
    """Get or create default sales provider."""
    global _default_provider
    if _default_provider is None:
        _default_provider = SalesDataProvider(use_test=use_test)
    return _default_provider

def read_sales_by_date_range(
    start_date: date, 
    end_date: date, 
    limit: Optional[int] = None, 
    include_lines: bool = True, 
    batch_size: int = 500,
    use_test: bool = False
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Module-level function for DatabaseUpdater compatibility.
    
    Args:
        start_date: Start date for the range
        end_date: End date for the range
        limit: Maximum number of orders to retrieve
        include_lines: Whether to include product lines
        batch_size: Batch size for line processing
        use_test: Whether to use test Odoo configuration
        
    Returns:
        Tuple: (orders_df, lines_df)
    """
    provider = SalesDataProvider(use_test=use_test)
    try:
        return provider.read_sales_by_date_range(
            start_date, end_date, limit, include_lines, batch_size
        )
    finally:
        provider.close()

def read_sales_by_day(day: date, use_test: bool = False) -> pd.DataFrame:
    """
    Module-level function for reading sales by day.
    
    Args:
        day: Date to retrieve sales for
        use_test: Whether to use test Odoo configuration
        
    Returns:
        DataFrame: Sales data for the specified day
    """
    provider = SalesDataProvider(use_test=use_test)
    try:
        return provider.read_sales_by_day(day)
    finally:
        provider.close()

def cleanup_sales_provider():
    """Clean up module-level provider."""
    global _default_provider
    if _default_provider is not None:
        _default_provider.close()
        _default_provider = None