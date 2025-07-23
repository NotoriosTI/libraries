"""
Refactored DatabaseUpdater for Sales Engine

Production-ready module for synchronizing Odoo sales data to PostgreSQL using 
the robust upsert pattern. This refactored version follows the product-engine 
design principles with proper primary key handling and timestamp-based sync.

Key improvements:
- Uses composite primary key (salesinvoiceid, items_product_sku) for upserts
- Implements proper INSERT ... ON CONFLICT DO UPDATE SET pattern
- Uses updated_at timestamp for incremental sync detection
- Follows product-engine architecture patterns
- Robust error handling and logging

Author: Bastian Ibañez (Refactored)
"""

import os
import time
import traceback
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps

import pandas as pd
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor, execute_values
import structlog

from .sales_integration import read_sales_by_date_range, cleanup_sales_provider
from config_manager import secrets

# Configure structured logging
logger = structlog.get_logger(__name__)


class DatabaseUpdaterError(Exception):
    """Base exception for DatabaseUpdater operations."""
    pass


class DatabaseConnectionError(DatabaseUpdaterError):
    """Raised when database connection fails."""
    pass


@dataclass
class UpdateResult:
    """Result of a database update operation."""
    success_count: int
    failure_count: int
    start_time: datetime
    end_time: datetime
    errors: List[str]
    upserts_performed: int = 0
    new_records: int = 0
    updated_records: int = 0

    @property
    def total_processed(self) -> int:
        return self.success_count + self.failure_count

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


def retry_on_db_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying database operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            log = structlog.get_logger()
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)
                        log.warning(
                            "Database operation failed, retrying...",
                            func_name=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            wait_seconds=wait_time,
                            error=str(e)
                        )
                        time.sleep(wait_time)
                    else:
                        log.error("Database operation failed after all retries", 
                                func_name=func.__name__, error=str(e))
                        break
                except Exception:
                    raise
            
            raise DatabaseConnectionError("Max retries exceeded for database operation.") from last_exception
        return wrapper
    return decorator


class DatabaseUpdater:
    """
    Refactored database updater using proper upsert pattern with composite primary key.
    
    This implementation follows the product-engine pattern with:
    - Composite primary key (salesinvoiceid, items_product_sku)
    - Timestamp-based incremental sync using updated_at column
    - INSERT ... ON CONFLICT DO UPDATE SET for atomic upserts
    - Robust error handling and connection pooling
    """

    def __init__(self, use_test_odoo: bool = False):
        """Initialize DatabaseUpdater with centralized configuration."""
        self.config = secrets
        self.logger = logger.bind(
            component="sales_database_updater",
            odoo_env="test" if use_test_odoo else "production"
        )
        self.use_test_odoo = use_test_odoo
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        
        self.logger.info(
            "DatabaseUpdater initialized",
            environment=self.config.ENVIRONMENT,
            use_test_odoo=self.use_test_odoo
        )

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get database connection parameters from centralized config."""
        try:
            db_config = self.config.get_database_config()
            db_config['port'] = int(db_config['port'])
            
            # Valid psycopg2 connection parameters
            valid_params = {
                'host', 'port', 'database', 'user', 'password', 'dbname',
                'connect_timeout', 'sslmode', 'application_name'
            }
            
            filtered_config = {k: v for k, v in db_config.items() if k in valid_params}
            
            self.logger.debug(
                "Database connection parameters prepared",
                host=filtered_config.get('host'),
                database=filtered_config.get('database')
            )
            
            return filtered_config
        except Exception as e:
            self.logger.error("Database configuration error", error=str(e))
            raise DatabaseConnectionError("Database configuration is incomplete.") from e

    def _setup_connection_pool(self):
        """Initialize database connection pool."""
        if self._connection_pool:
            return
            
        try:
            params = self._get_connection_params()
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2, 
                maxconn=10, 
                connect_timeout=30,
                **params
            )
            self.logger.info("Database connection pool created", 
                           host=params.get('host'), 
                           database=params.get('database'))
        except Exception as e:
            self.logger.error("Failed to create connection pool", error=str(e))
            raise DatabaseConnectionError("Failed to create connection pool.") from e

    @contextmanager
    def get_connection(self):
        """Context manager for pooled database connections."""
        if not self._connection_pool:
            self._setup_connection_pool()

        conn = None
        try:
            conn = self._connection_pool.getconn()
            yield conn
            conn.commit()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            self.logger.error("Database transaction failed", error=str(e))
            raise DatabaseConnectionError("Database transaction failed.") from e
        finally:
            if conn:
                self._connection_pool.putconn(conn)

    @retry_on_db_error()
    def get_last_sync_time(self) -> Optional[datetime]:
        """
        Get the most recent updated_at timestamp for incremental sync.
        
        This replaces the old logic that used issueddate and instead uses
        the updated_at column to determine when the last sync occurred.
        
        Returns:
            The most recent updated_at timestamp, or None if no records exist.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT MAX(updated_at) as last_sync_time
                    FROM sales_items 
                    WHERE updated_at IS NOT NULL
                """)
                result = cursor.fetchone()
                last_sync_time = result['last_sync_time'] if result else None
                
                if last_sync_time:
                    self.logger.info("Last sync time retrieved", 
                                   last_sync_time=last_sync_time.isoformat())
                else:
                    self.logger.info("No previous sync time found - will perform full sync")
                
                return last_sync_time

    def prepare_data_for_upsert(self, orders_df: pd.DataFrame, lines_df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare combined sales data for upsert operations.
        
        Args:
            orders_df: Orders DataFrame from Odoo
            lines_df: Order lines DataFrame from Odoo
            
        Returns:
            Combined DataFrame ready for database upsert
        """
        if orders_df.empty or lines_df.empty:
            self.logger.warning("Empty DataFrames provided for upsert preparation")
            return pd.DataFrame()

        # Merge orders and lines on order_id
        combined_df = pd.merge(orders_df, lines_df, on='order_id', how='inner')
        
        if combined_df.empty:
            self.logger.warning("No matching records after merge")
            return combined_df

        # Ensure required columns exist with proper defaults
        required_columns = {
            'salesinvoiceid': '',
            'doctype_name': 'Factura',
            'docnumber': '',
            'customer_customerid': 0,
            'customer_name': '',
            'customer_vatid': '',
            'salesman_name': '',
            'term_name': '',
            'warehouse_name': '',
            'totals_net': 0.0,
            'totals_vat': 0.0,
            'total_total': 0.0,
            'items_product_description': '',
            'items_product_sku': '',
            'items_quantity': 0.0,
            'items_unitprice': 0.0,
            'issueddate': None,
            'sales_channel': ''
        }

        for col, default_value in required_columns.items():
            if col not in combined_df.columns:
                combined_df[col] = default_value

        # Clean and validate the data
        combined_df = self._clean_sales_data(combined_df)
        
        self.logger.info("Data prepared for upsert", 
                       total_records=len(combined_df),
                       columns=list(combined_df.columns))
        
        return combined_df[list(required_columns.keys())]

    def _clean_sales_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate sales data before upsert."""
        initial_count = len(df)
        
        # Remove records with missing primary key components
        df = df.dropna(subset=['salesinvoiceid', 'items_product_sku'])
        
        # Remove records with empty or invalid primary key values
        df = df[
            (df['salesinvoiceid'] != '') & 
            (df['salesinvoiceid'] != 'None') &
            (df['items_product_sku'] != '') & 
            (df['items_product_sku'] != 'None')
        ]
        
        # Convert string primary key fields to proper format
        df['salesinvoiceid'] = df['salesinvoiceid'].astype(str).str.strip()
        df['items_product_sku'] = df['items_product_sku'].astype(str).str.strip()
        
        # Handle numeric fields
        numeric_fields = ['customer_customerid', 'totals_net', 'totals_vat', 
                         'total_total', 'items_quantity', 'items_unitprice']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)
        
        # Handle date fields
        if 'issueddate' in df.columns:
            df['issueddate'] = pd.to_datetime(df['issueddate'], errors='coerce')
        
        cleaned_count = len(df)
        if cleaned_count != initial_count:
            self.logger.warning("Records filtered during cleaning", 
                              initial_count=initial_count, 
                              final_count=cleaned_count,
                              filtered_count=initial_count - cleaned_count)
        
        return df

    @retry_on_db_error()
    def bulk_upsert_sales_data(self, df: pd.DataFrame) -> Tuple[int, int, int]:
        """
        Perform bulk upsert using INSERT ... ON CONFLICT DO UPDATE SET.
        
        Args:
            df: DataFrame with sales data to upsert
            
        Returns:
            Tuple of (total_upserts, new_records, updated_records)
        """
        if df.empty:
            return 0, 0, 0

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                self.logger.info("Starting bulk upsert operation", record_count=len(df))
                
                # Prepare the upsert SQL with proper conflict resolution
                upsert_sql = """
                INSERT INTO sales_items (
                    salesinvoiceid, doctype_name, docnumber, customer_customerid,
                    customer_name, customer_vatid, salesman_name, term_name,
                    warehouse_name, totals_net, totals_vat, total_total,
                    items_product_description, items_product_sku, items_quantity,
                    items_unitprice, issueddate, sales_channel
                ) VALUES %s
                ON CONFLICT (salesinvoiceid, items_product_sku) 
                DO UPDATE SET
                    doctype_name = EXCLUDED.doctype_name,
                    docnumber = EXCLUDED.docnumber,
                    customer_customerid = EXCLUDED.customer_customerid,
                    customer_name = EXCLUDED.customer_name,
                    customer_vatid = EXCLUDED.customer_vatid,
                    salesman_name = EXCLUDED.salesman_name,
                    term_name = EXCLUDED.term_name,
                    warehouse_name = EXCLUDED.warehouse_name,
                    totals_net = EXCLUDED.totals_net,
                    totals_vat = EXCLUDED.totals_vat,
                    total_total = EXCLUDED.total_total,
                    items_product_description = EXCLUDED.items_product_description,
                    items_quantity = EXCLUDED.items_quantity,
                    items_unitprice = EXCLUDED.items_unitprice,
                    issueddate = EXCLUDED.issueddate,
                    sales_channel = EXCLUDED.sales_channel,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING 
                    salesinvoiceid, 
                    items_product_sku,
                    (xmax = 0) AS was_inserted
                """

                # Prepare data tuples
                data_tuples = []
                for _, row in df.iterrows():
                    data_tuple = (
                        row['salesinvoiceid'], row['doctype_name'], row['docnumber'],
                        int(row['customer_customerid']), row['customer_name'], row['customer_vatid'],
                        row['salesman_name'], row['term_name'], row['warehouse_name'],
                        float(row['totals_net']), float(row['totals_vat']), float(row['total_total']),
                        row['items_product_description'], row['items_product_sku'],
                        float(row['items_quantity']), float(row['items_unitprice']),
                        row['issueddate'], row['sales_channel']
                    )
                    data_tuples.append(data_tuple)

                # Execute the bulk upsert
                execute_values(
                    cursor, upsert_sql, data_tuples,
                    template=None, page_size=100
                )

                # Count the results
                results = cursor.fetchall()
                total_upserts = len(results)
                
                # Count new vs updated records
                new_records = sum(1 for result in results if result[2])  # was_inserted = True
                updated_records = total_upserts - new_records

                self.logger.info("Bulk upsert completed",
                               total_upserts=total_upserts,
                               new_records=new_records,
                               updated_records=updated_records)

                return total_upserts, new_records, updated_records

    def run_update(self, start_date_override: Optional[date] = None, 
                   force_full_sync: bool = False) -> UpdateResult:
        """
        Main orchestration method for the sales data sync process.
        
        Args:
            start_date_override: Optional start date override
            force_full_sync: If True, ignores last sync time and syncs all data
            
        Returns:
            UpdateResult with sync statistics
        """
        run_start_time = datetime.now()
        self.logger.info("Sales data sync process starting...",
                        force_full_sync=force_full_sync,
                        start_date_override=str(start_date_override) if start_date_override else None)

        try:
            # Step 1: Determine sync start date
            if force_full_sync or start_date_override:
                start_date = start_date_override or (date.today() - timedelta(days=90))
                self.logger.info("Using full sync or override date", start_date=str(start_date))
            else:
                # Use incremental sync based on last updated_at timestamp
                last_sync_time = self.get_last_sync_time()
                if last_sync_time:
                    # Add a small buffer to catch any records that might have been missed
                    start_date = (last_sync_time - timedelta(hours=1)).date()
                    self.logger.info("Using incremental sync", 
                                   last_sync_time=last_sync_time.isoformat(),
                                   start_date=str(start_date))
                else:
                    # No previous sync, start from 30 days ago
                    start_date = date.today() - timedelta(days=30)
                    self.logger.info("No previous sync found, using default range", 
                                   start_date=str(start_date))

            end_date = date.today()
            
            if start_date > end_date:
                self.logger.info("Database is already up-to-date")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            # Step 2: Fetch sales data from Odoo
            self.logger.info("Fetching sales data from Odoo",
                           start_date=str(start_date),
                           end_date=str(end_date))

            orders_df, lines_df = read_sales_by_date_range(
                start_date, end_date, 
                use_test=self.use_test_odoo
            )

            if orders_df.empty:
                self.logger.info("No new sales data found")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            # Step 3: Prepare data for upsert
            combined_df = self.prepare_data_for_upsert(orders_df, lines_df)
            
            if combined_df.empty:
                self.logger.info("No valid records to sync after data preparation")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            # Step 4: Perform bulk upsert
            total_upserts, new_records, updated_records = self.bulk_upsert_sales_data(combined_df)

            # Step 5: Create result summary
            run_end_time = datetime.now()
            result = UpdateResult(
                success_count=total_upserts,
                failure_count=0,
                start_time=run_start_time,
                end_time=run_end_time,
                errors=[],
                upserts_performed=total_upserts,
                new_records=new_records,
                updated_records=updated_records
            )

            self.logger.info("Sales data sync completed successfully",
                           total_upserts=total_upserts,
                           new_records=new_records,
                           updated_records=updated_records,
                           duration_seconds=result.duration_seconds)

            return result

        except Exception as e:
            run_end_time = datetime.now()
            error_msg = str(e)
            
            self.logger.error("Sales data sync failed",
                            error=error_msg,
                            duration_seconds=(run_end_time - run_start_time).total_seconds(),
                            exc_info=True)

            return UpdateResult(0, 1, run_start_time, run_end_time, [error_msg])

    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    result = cursor.fetchone()
                    self.logger.info("Database connection test successful", 
                                   version=result[0] if result else "Unknown")
                    return True
        except Exception as e:
            self.logger.error("Database connection test failed", error=str(e))
            return False

    def close(self):
        """Clean up database connections and resources."""
        try:
            if self._connection_pool:
                self._connection_pool.closeall()
                self.logger.info("Database connection pool closed")
            cleanup_sales_provider()
        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point for the refactored sales database updater."""
    main_logger = logger.bind(component="main")
    main_logger.info("Refactored Sales Database Updater starting...")

    try:
        # Configuration from environment
        use_test = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
        force_full_sync = os.getenv('FORCE_FULL_SYNC', 'false').lower() == 'true'
        test_connections_only = os.getenv('TEST_CONNECTIONS_ONLY', 'false').lower() == 'true'

        main_logger.info("Configuration loaded",
                        use_test_odoo=use_test,
                        force_full_sync=force_full_sync,
                        test_connections_only=test_connections_only)

        with DatabaseUpdater(use_test_odoo=use_test) as updater:
            if test_connections_only:
                # Test connections only
                main_logger.info("Testing connections only...")
                if updater.test_connection():
                    main_logger.info("Connection test successful")
                    return 0
                else:
                    main_logger.error("Connection test failed")
                    return 1
            else:
                # Run full sync
                result = updater.run_update(force_full_sync=force_full_sync)

                main_logger.info("Sales sync completed",
                               status="SUCCESS" if not result.errors else "FAILURE",
                               total_upserts=result.upserts_performed,
                               new_records=result.new_records,
                               updated_records=result.updated_records,
                               duration_seconds=round(result.duration_seconds, 2),
                               errors=result.errors)

                return 0 if not result.errors else 1

    except Exception as e:
        main_logger.error("Unhandled exception in sales updater", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())