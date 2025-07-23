"""
Refactored DatabaseUpdater for Sales Engine

This module is now responsible ONLY for database interactions. All data fetching
and preparation logic has been moved to the 'odoo-api' library.

Key Features:
- Connects to and manages the PostgreSQL database connection pool.
- Performs efficient, atomic bulk upserts using INSERT ... ON CONFLICT.
- Determines the correct date range for incremental syncs.
- Does NOT contain any Odoo-specific data transformation logic.

Author: Bastian Ibañez (Refactored)
"""
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps

import pandas as pd
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor, execute_values
import structlog

# --- CORRECTED IMPORTS ---
# Fetches data from the refactored, external odoo-api library
from odoo_api.sales import OdooSales
# Fetches configuration from the external config-manager library
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
                        import time
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
    Manages the synchronization of sales data from Odoo to the PostgreSQL database.
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
        
        # --- NEW: Instantiate the OdooSales class ---
        odoo_config = self.config.get_odoo_config(use_test=self.use_test_odoo)
        self.odoo_api = OdooSales(
            db=odoo_config['db'],
            url=odoo_config['url'],
            username=odoo_config['username'],
            password=odoo_config['password']
        )
        
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
            return db_config
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
                minconn=2, maxconn=10, connect_timeout=30, **params
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
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT MAX(updated_at) as last_sync_time FROM sales_items WHERE updated_at IS NOT NULL")
                result = cursor.fetchone()
                last_sync_time = result['last_sync_time'] if result else None
                
                if last_sync_time:
                    self.logger.info("Last sync time retrieved", 
                                     last_sync_time=last_sync_time.isoformat())
                else:
                    self.logger.info("No previous sync time found - will perform full sync")
                
                return last_sync_time

    @retry_on_db_error()
    def bulk_upsert_sales_data(self, df: pd.DataFrame) -> Tuple[int, int, int]:
        """
        Perform bulk upsert using INSERT ... ON CONFLICT DO UPDATE SET.
        """
        if df.empty:
            return 0, 0, 0

        # --- IMPROVEMENT: Deduplicate DataFrame before upsert ---
        original_count = len(df)
        df_deduped = df.drop_duplicates(subset=['salesinvoiceid', 'items_product_sku'], keep='last').copy()
        deduped_count = len(df_deduped)
        duplicates_removed = original_count - deduped_count
        
        if duplicates_removed > 0:
            self.logger.info("Duplicates removed from DataFrame before upsert",
                           duplicates_removed=duplicates_removed,
                           original_count=original_count,
                           deduped_count=deduped_count)

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                self.logger.info("Starting bulk upsert operation", record_count=len(df_deduped))
                
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

                # Convert data to tuples using deduplicated DataFrame
                data_tuples = []
                for _, row in df_deduped.iterrows():
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

                execute_values(
                    cursor, upsert_sql, data_tuples,
                    template=None, page_size=1000
                )

                results = cursor.fetchall()
                total_upserts = len(results)
                new_records = sum(1 for result in results if result[2])
                updated_records = total_upserts - new_records

                self.logger.info("Bulk upsert completed",
                                 total_upserts=total_upserts,
                                 new_records=new_records,
                                 updated_records=updated_records,
                                 duplicates_removed_before_upsert=duplicates_removed)

                return total_upserts, new_records, updated_records

    def run_update(self, start_date_override: Optional[date] = None, 
                   force_full_sync: bool = False) -> UpdateResult:
        """
        Main orchestration method for the sales data sync process.
        """
        run_start_time = datetime.now()
        self.logger.info("Sales data sync process starting...",
                         force_full_sync=force_full_sync,
                         start_date_override=str(start_date_override) if start_date_override else None)

        try:
            # Step 1: Determine sync start date
            if force_full_sync or start_date_override:
                start_date = start_date_override or (date.today() - timedelta(days=90))
            else:
                last_sync_time = self.get_last_sync_time()
                if last_sync_time:
                    start_date = (last_sync_time - timedelta(hours=1)).date()
                else:
                    start_date = date.today() - timedelta(days=30)
            
            end_date = date.today()
            self.logger.info("Determined sync date range", start_date=str(start_date), end_date=str(end_date))

            if start_date > end_date:
                self.logger.info("Database is already up-to-date")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            # --- STEP 2: SIMPLIFIED DATA FETCHING ---
            self.logger.info("Fetching prepared sales data from Odoo...")
            sales_data_df = self.odoo_api.read_sales_by_date_range(start_date, end_date)

            if sales_data_df.empty:
                self.logger.info("No new sales data found or no valid records to sync.")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            # --- STEP 3: PERFORM BULK UPSERT ---
            # The preparation step is no longer needed.
            total_upserts, new_records, updated_records = self.bulk_upsert_sales_data(sales_data_df)

            # Step 4: Create result summary
            run_end_time = datetime.now()
            result = UpdateResult(
                success_count=total_upserts, failure_count=0,
                start_time=run_start_time, end_time=run_end_time,
                errors=[], upserts_performed=total_upserts,
                new_records=new_records, updated_records=updated_records
            )

            self.logger.info("Sales data sync completed successfully", **result.__dict__)
            return result

        except Exception as e:
            run_end_time = datetime.now()
            error_msg = str(e)
            self.logger.error("Sales data sync failed", error=error_msg, exc_info=True)
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
        """Clean up database and Odoo connections."""
        try:
            if self._connection_pool:
                self._connection_pool.closeall()
                self.logger.info("Database connection pool closed")
            
            # --- NEW: Disconnect from Odoo API ---
            if self.odoo_api:
                self.odoo_api.disconnect()
                self.logger.info("Odoo API connection closed")

        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
