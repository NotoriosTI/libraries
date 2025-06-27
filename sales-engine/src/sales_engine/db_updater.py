"""
DatabaseUpdater

Production-ready module for connecting Odoo sales data to PostgreSQL on GCP.

This module provides a robust DatabaseUpdater class with comprehensive error
handling, logging, Google Cloud integration, efficient database operations,
and anti-duplication logic.

Author: Bastian Ibañez

Dependencies:
    - pandas
    - psycopg2-binary
    - google-cloud-secret-manager
    - sales.py
"""

# Standard library imports
import logging 
import io 
import os 
import time 
import traceback 
from datetime import datetime, date 
from typing import Dict, List, Optional, Any, Tuple, Iterator 
from dataclasses import dataclass 
from contextlib import contextmanager 
from functools import wraps

# Third-party imports
import pandas as pd 
import psycopg2 
import psycopg2.pool 
from psycopg2.extras import execute_values 
from google.cloud import secretmanager 
from google.api_core import exceptions as gcp_exceptions 
import structlog

# Local imports
from .sales_integration import read_sales_by_date_range
from .secret_manager import SecretManagerClient

# Configure structured logging for production
structlog.configure( 
    processors=[ 
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

# Custom Exceptions
class DatabaseUpdaterError(Exception):
    """Base exception for DatabaseUpdater operations."""
    pass
class DatabaseConnectionError(DatabaseUpdaterError):
    """Raised when database connection fails."""
    pass
class DataValidationError(DatabaseUpdaterError):
    """Raised when data validation fails."""
    pass

@dataclass
class UpdateResult:
    """Result of database update operation."""
    success_count: int
    failure_count: int
    total_time: float
    start_time: datetime
    end_time: datetime
    errors: List[str]
    
    @property
    def total_processed(self) -> int:
        return self.success_count + self.failure_count
    
class StringIteratorIO(io.TextIOBase):
    """
    File-like object that reads from a string iterator for memory-efficient bulk loading.
    """
    def __init__(self, iter: Iterator[str]):
        self._iter = iter
        self._buff = ''

    def readable(self) -> bool:
        return True
    
    def _read1(self, n: Optional[int] = None) -> str:
        while not self._buff:
            try:
                self._buff = next(self._iter)
            except StopIteration:
                break
        ret = self._buff[:n]
        self._buff = self._buff[len(ret):]
        return ret
    
    def read(self, n: Optional[int] = None) -> str:
        line = []
        if n is None or n < 0:
            while True:
                m = self._read1()
                if not m:
                    break
                line.append(m)
        else:
            while n > 0:
                m = self._read1(n)
                if not m:
                    break
                n -= len(m)
                line.append(m)
        return ''.join(line) 

def retry_on_db_error(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying database operations on transient errors.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)
                        logging.warning(f"Database operation retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                        time.sleep(wait_time)
                        continue
                    break
                except Exception as e:
                    # Don't retry on non-transient errors
                    raise
            raise DatabaseConnectionError(f"Max retries exceeded") from last_exception
        return wrapper
    return decorator

class DatabaseUpdater:
    """
    Production-ready database updater for connecting Odoo sales data to PostgreSQL on GCP.
    This class provides comprehensive functionality for:
    - Secure connection to Cloud SQL PostgreSQL via Cloud SQL Auth Proxy
    - Credential management through Google Secret Manager  
    - Anti-duplication logic to prevent duplicate records
    - Efficient bulk loading using psycopg2 copy_from
    - Data processing and validation
    - Comprehensive error handling and logging

    Example:
        >>> updater = DatabaseUpdater()
        >>> result = updater.run_update()
        >>> print(f"Processed {result.total_processed} records")
    """

    def __init__(self, project_id: Optional[str] = None, connection_params: Optional[Dict] = None):
        """
        Initialize DatabaseUpdater.
        
        Args:
            project_id: Google Cloud project ID for Secret Manager
            connection_params: Optional database connection parameters (for testing)
        """
        self.logger = structlog.get_logger().bind(component="database_updater")
        self.project_id = project_id
        self.connection_params = connection_params
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self.secret_manager = SecretManagerClient(project_id) if not connection_params else None
        
        # Configuration
        self.batch_size = 1000
        self.max_retries = 3
        
        self.logger.info("DatabaseUpdater initialized")

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get database connection parameters from Secret Manager or provided params."""
        if self.connection_params:
            return self.connection_params
        
        if not self.secret_manager:
            raise DatabaseConnectionError("No connection parameters or Secret Manager client available")
        
        credentials = self.secret_manager.get_database_credentials()
        return {
            'host': credentials['host'],
            'port': int(credentials['port']),
            'database': credentials['database'],
            'user': credentials['user'],
            'password': credentials['password']
        }

    def _setup_connection_pool(self):
        """Initialize database connection pool."""
        try:
            params = self._get_connection_params()
            
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=params['host'],
                port=params['port'],
                database=params['database'],
                user=params['user'],
                password=params['password'],
                connect_timeout=30
            )
            
            self.logger.info("Database connection pool created", 
                             host=params['host'], database=params['database'])
            
        except Exception as e:
            self.logger.error("Failed to create connection pool", error=str(e))
            raise DatabaseConnectionError(f"Failed to create connection pool: {e}")

    @contextmanager
    def get_connection(self):
        """Context manager for getting pooled database connections."""
        if not self._connection_pool:
            self._setup_connection_pool()
        
        conn = None
        try:
            conn = self._connection_pool.getconn()
            if conn.closed:
                # Connection is stale, get a new one
                self._connection_pool.putconn(conn, close=True)
                conn = self._connection_pool.getconn()
            yield conn
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            self.logger.error("Database connection error", error=str(e))
            raise DatabaseConnectionError(f"Database connection error: {e}")
        finally:
            if conn:
                self._connection_pool.putconn(conn)

    @retry_on_db_error(max_retries=3)
    def get_latest_date_records(self) -> Tuple[Optional[date], set]:
        """
        Get the most recent issuedDate and existing (salesInvoiceId, items_product_sku) pairs
        for that date to implement anti-duplication logic.
        
        Returns:
            Tuple of (latest_date, set of (invoice_id, sku) pairs)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Get the most recent date
                    cursor.execute("""
                        SELECT MAX(issuedDate) as latest_date
                        FROM sales_items
                        WHERE issuedDate IS NOT NULL
                    """)
                    
                    result = cursor.fetchone()
                    latest_date = result[0] if result and result[0] else None
                    
                    if not latest_date:
                        self.logger.info("No existing records found")
                        return None, set()
                    
                    # Get existing (salesInvoiceId, items_product_sku) pairs for latest date
                    cursor.execute("""
                        SELECT salesInvoiceId, items_product_sku 
                        FROM sales_items 
                        WHERE issuedDate = %s
                    """, (latest_date,))
                    
                    existing_pairs = set(cursor.fetchall())
                    
                    self.logger.info("Retrieved existing records for anti-duplication", 
                                     latest_date=str(latest_date), 
                                     existing_pairs_count=len(existing_pairs))
                    
                    return latest_date, existing_pairs
                    
        except Exception as e:
            self.logger.error("Failed to get latest date records", error=str(e))
            raise DatabaseConnectionError(f"Failed to query existing records: {e}")

    def process_and_combine_dataframes(self, orders_df: pd.DataFrame, lines_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process and combine orders and lines DataFrames into sales_items format.
        
        Args:
            orders_df: DataFrame containing order data
            lines_df: DataFrame containing line item data
            
        Returns:
            Combined DataFrame matching sales_items table structure
        """
        try:
            self.logger.info("Processing and combining DataFrames", 
                             orders_count=len(orders_df), lines_count=len(lines_df))
            
            # Validate required columns exist
            required_order_cols = ['salesInvoiceId']  # Add other required columns
            required_line_cols = ['salesInvoiceId', 'items_product_sku']  # Add other required columns
            
            missing_order_cols = [col for col in required_order_cols if col not in orders_df.columns]
            missing_line_cols = [col for col in required_line_cols if col not in lines_df.columns]
            
            if missing_order_cols:
                raise DataValidationError(f"Missing required columns in orders: {missing_order_cols}")
            if missing_line_cols:
                raise DataValidationError(f"Missing required columns in lines: {missing_line_cols}")
            
            # Optimize DataFrames for joining
            orders_df = orders_df.sort_values('salesInvoiceId')
            lines_df = lines_df.sort_values('salesInvoiceId')
            
            # Perform efficient merge
            combined_df = pd.merge(
                orders_df, 
                lines_df, 
                on='salesInvoiceId', 
                how='inner',  # Only keep records with matching orders and lines
                suffixes=('_order', '_line'),
                validate='one_to_many'
            )
            
            # Map to sales_items table structure
            sales_items_df = pd.DataFrame()
            
            # Map columns - adjust these mappings based on your actual column names
            column_mapping = {
                'salesInvoiceId': 'salesInvoiceId',
                'doctype_name': 'doctype_name',
                'docnumber': 'docnumber', 
                'customer_customerid': 'customer_customerid',
                'customer_name': 'customer_name',
                'customer_vatid': 'customer_vatid',
                'salesman_name': 'salesman_name',
                'term_name': 'term_name',
                'warehouse_name': 'warehouse_name',
                'totals_net': 'totals_net',
                'totals_vat': 'totals_vat',
                'total_total': 'total_total',
                'items_product_description': 'items_product_description',
                'items_product_sku': 'items_product_sku',
                'items_quantity': 'items_quantity',
                'items_unitPrice': 'items_unitPrice',
                'issuedDate': 'issuedDate',
                'sales_channel': 'sales_channel'
            }
            
            # Apply column mapping with error handling
            for target_col, source_col in column_mapping.items():
                if source_col in combined_df.columns:
                    sales_items_df[target_col] = combined_df[source_col]
                else:
                    # Handle missing columns with defaults
                    if target_col in ['salesman_name', 'term_name']:
                        sales_items_df[target_col] = ''
                    elif target_col in ['totals_net', 'totals_vat', 'total_total', 'items_quantity', 'items_unitPrice']:
                        sales_items_df[target_col] = 0.0
                    else:
                        self.logger.warning("Missing column in source data", column=source_col)
                        sales_items_df[target_col] = None
            
            # Data type validation and conversion
            sales_items_df = self._validate_and_clean_data(sales_items_df)
            
            self.logger.info("DataFrames processed and combined successfully", 
                             combined_count=len(sales_items_df))
            
            return sales_items_df
            
        except Exception as e:
            self.logger.error("Failed to process and combine DataFrames", error=str(e))
            raise DataValidationError(f"Failed to process DataFrames: {e}")

    def _validate_and_clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean data according to sales_items schema."""
        try:
            # Handle missing values
            df['salesman_name'] = df['salesman_name'].fillna('')
            df['term_name'] = df['term_name'].fillna('')
            df['warehouse_name'] = df['warehouse_name'].fillna('')
            df['sales_channel'] = df['sales_channel'].fillna('')
            
            # Convert numeric columns
            numeric_columns = [
                'customer_customerid', 'totals_net', 'totals_vat', 
                'total_total', 'items_quantity', 'items_unitPrice'
            ]
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Convert date columns
            if 'issuedDate' in df.columns:
                df['issuedDate'] = pd.to_datetime(df['issuedDate'], errors='coerce')
            
            # Validate required fields are not null
            required_fields = ['salesInvoiceId', 'items_product_sku']
            for field in required_fields:
                if df[field].isnull().any():
                    null_count = df[field].isnull().sum()
                    self.logger.warning("Null values found in required field", 
                                        field=field, null_count=null_count)
                    df = df.dropna(subset=[field])
            
            return df
            
        except Exception as e:
            self.logger.error("Data validation failed", error=str(e))
            raise DataValidationError(f"Data validation failed: {e}")

    def filter_duplicate_records(self, df: pd.DataFrame, existing_pairs: set) -> pd.DataFrame:
        """
        Filter out records that already exist in the database.
        
        Args:
            df: DataFrame to filter
            existing_pairs: Set of (salesInvoiceId, items_product_sku) pairs that exist
            
        Returns:
            Filtered DataFrame with duplicates removed
        """
        if not existing_pairs:
            return df
        
        initial_count = len(df)
        
        # Create composite key for filtering
        df_composite = df[['salesInvoiceId', 'items_product_sku']].apply(
            lambda x: tuple(x), axis=1
        )
        
        # Filter out existing combinations
        mask = ~df_composite.isin(existing_pairs)
        filtered_df = df[mask].copy()
        
        filtered_count = len(filtered_df)
        duplicate_count = initial_count - filtered_count
        
        self.logger.info("Filtered duplicate records", 
                         initial_count=initial_count,
                         filtered_count=filtered_count, 
                         duplicates_removed=duplicate_count)
        
        return filtered_df

    def _clean_csv_value(self, value: Any) -> str:
        """Clean and escape CSV values for PostgreSQL COPY."""
        if pd.isna(value) or value is None:
            return '\\N'  # PostgreSQL NULL representation
        
        value_str = str(value)
        # Escape special characters
        value_str = value_str.replace('\n', '\\n')
        value_str = value_str.replace('\r', '\\r')
        value_str = value_str.replace('\t', '\\t')
        value_str = value_str.replace('|', '\\|')
        
        return value_str

    @retry_on_db_error(max_retries=3)
    def bulk_load_data(self, df: pd.DataFrame) -> int:
        """
        Efficiently load data using psycopg2 copy_from with StringIteratorIO.
        
        Args:
            df: DataFrame to load
            
        Returns:
            Number of records loaded
        """
        if df.empty:
            self.logger.info("No data to load")
            return 0
        
        try:
            # Define column order for sales_items table
            columns = [
                'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
                'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
                'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
                'items_product_description', 'items_product_sku', 'items_quantity',
                'items_unitPrice', 'issuedDate', 'sales_channel'
            ]
            
            # Prepare data iterator for memory efficiency
            def data_iterator():
                for _, row in df.iterrows():
                    yield '|'.join([self._clean_csv_value(row.get(col)) for col in columns]) + '\n'
            
            csv_iterator = StringIteratorIO(data_iterator())
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    self.logger.info("Starting bulk data load", record_count=len(df))
                    
                    start_time = time.time()
                    
                    cursor.copy_from(
                        csv_iterator,
                        'sales_items',
                        sep='|',
                        null='\\N',
                        columns=columns
                    )
                    
                    conn.commit()
                    load_time = time.time() - start_time
                    
                    self.logger.info("Bulk data load completed successfully", 
                                     records_loaded=len(df), 
                                     load_time_seconds=round(load_time, 2))
                    
                    return len(df)
                    
        except Exception as e:
            self.logger.error("Bulk data load failed", error=str(e), traceback=traceback.format_exc())
            raise DatabaseConnectionError(f"Bulk data load failed: {e}")

    def run_update(self, start_date: Optional[date] = None) -> UpdateResult:
        """
        Main orchestration method to run the complete update process.
        
        Args:
            start_date: Optional start date for data retrieval (defaults to latest + 1 day)
            
        Returns:
            UpdateResult with operation statistics
        """
        start_time = datetime.now()
        errors = []
        
        try:
            self.logger.info("Starting database update process")
            
            # Step 1: Connect to database and get latest records
            latest_date, existing_pairs = self.get_latest_date_records()
            
            # Step 2: Determine date range for new data
            if not start_date:
                if latest_date:
                    start_date = latest_date + pd.Timedelta(days=1)
                else:
                    start_date = date.today() - pd.Timedelta(days=30)  # Default to last 30 days
            
            end_date = date.today()
            
            self.logger.info("Retrieving sales data", 
                             start_date=str(start_date), end_date=str(end_date))
            
            # Step 3: Call sales.py to get new data
            try:
                sales_data = read_sales_by_date_range(start_date, end_date)
                if isinstance(sales_data, tuple) and len(sales_data) == 2:
                    orders_df, lines_df = sales_data
                else:
                    raise DatabaseUpdaterError("sales.read_sales_by_date_range returned unexpected format")
            except Exception as e:
                raise DatabaseUpdaterError(f"Failed to retrieve sales data: {e}")
            
            if orders_df.empty and lines_df.empty:
                self.logger.info("No new sales data found")
                return UpdateResult(
                    success_count=0,
                    failure_count=0,
                    total_time=0.0,
                    start_time=start_time,
                    end_time=datetime.now(),
                    errors=[]
                )
            
            # Step 4: Process and combine data
            combined_df = self.process_and_combine_dataframes(orders_df, lines_df)
            
            # Step 5: Filter out existing records
            filtered_df = self.filter_duplicate_records(combined_df, existing_pairs)
            
            if filtered_df.empty:
                self.logger.info("No new records to insert after deduplication")
                return UpdateResult(
                    success_count=0,
                    failure_count=0,
                    total_time=(datetime.now() - start_time).total_seconds(),
                    start_time=start_time,
                    end_time=datetime.now(),
                    errors=[]
                )
            
            # Step 6: Load data to database
            records_loaded = self.bulk_load_data(filtered_df)
            
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            self.logger.info("Database update completed successfully", 
                             records_loaded=records_loaded, 
                             total_time_seconds=round(total_time, 2))
            
            return UpdateResult(
                success_count=records_loaded,
                failure_count=0,
                total_time=total_time,
                start_time=start_time,
                end_time=end_time,
                errors=errors
            )
            
        except Exception as e:
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            error_msg = f"Database update failed: {str(e)}"
            errors.append(error_msg)
            
            self.logger.error("Database update failed", 
                              error=str(e), 
                              traceback=traceback.format_exc(),
                              total_time_seconds=round(total_time, 2))
            
            return UpdateResult(
                success_count=0,
                failure_count=1,
                total_time=total_time,
                start_time=start_time,
                end_time=end_time,
                errors=errors
            )

    def close(self):
        """Clean up database connections."""
        try:
            if self._connection_pool:
                self._connection_pool.closeall()
                self.logger.info("Database connections closed")
        except Exception as e:
            self.logger.error("Error closing database connections", error=str(e))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()