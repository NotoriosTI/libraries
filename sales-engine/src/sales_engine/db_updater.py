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
    - structlog
    - odoo-api
    - config-manager
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
from google.api_core import exceptions as gcp_exceptions
import structlog

# Local imports
from .sales_integration import read_sales_by_date_range, cleanup_sales_provider
from .secret_manager import SecretManagerClient, SecretManagerError
# Assuming a setup_logging function exists in your config_manager
from config_manager import secrets # Using the singleton instance

# --- Custom Exceptions ---
class DatabaseUpdaterError(Exception):
    """Base exception for DatabaseUpdater operations."""
    pass

class DatabaseConnectionError(DatabaseUpdaterError):
    """Raised when database connection fails."""
    pass

class DataValidationError(DatabaseUpdaterError):
    """Raised when data validation fails."""
    pass


# --- Data Structures ---
@dataclass
class UpdateResult:
    """Result of a database update operation."""
    success_count: int
    failure_count: int
    start_time: datetime
    end_time: datetime
    errors: List[str]

    @property
    def total_processed(self) -> int:
        """Total number of records processed (successful + failed)."""
        return self.success_count + self.failure_count

    @property
    def duration_seconds(self) -> float:
        """The total duration of the operation in seconds."""
        return (self.end_time - self.start_time).total_seconds()


# --- Helper Classes & Decorators ---
class StringIteratorIO(io.TextIOBase):
    """
    File-like object that reads from a string iterator for memory-efficient
    bulk loading with psycopg2.copy_from.
    """
    def __init__(self, iter: Iterator[str]):
        self._iter = iter
        self._buff = ''

    def readable(self) -> bool:
        return True

    def read(self, n: Optional[int] = None) -> str:
        # Simplified and more efficient read implementation
        try:
            while n is None or len(self._buff) < n:
                self._buff += next(self._iter)
        except StopIteration:
            pass
        ret = self._buff[:n]
        self._buff = self._buff[len(ret):]
        return ret


def retry_on_db_error(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying database operations on transient errors with
    exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            logger = structlog.get_logger()
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(
                            "Database operation failed, retrying...",
                            func_name=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            wait_seconds=wait_time,
                            error=str(e)
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            "Database operation failed after all retries.",
                            func_name=func.__name__,
                            error=str(e)
                        )
                        break
                except Exception:
                    # Don't retry on non-transient errors (e.g., SQL syntax error)
                    raise
            raise DatabaseConnectionError("Max retries exceeded for database operation.") from last_exception
        return wrapper
    return decorator


# --- Main Class ---
class DatabaseUpdater:
    """
    Production-ready database updater for connecting Odoo sales data to PostgreSQL on GCP.
    """

    def __init__(self, use_test_odoo: bool = False):
        """
        Initialize DatabaseUpdater.

        Args:
            use_test_odoo: If True, connects to the test Odoo instance as
                           defined in the config.
        """
        # Uses the singleton 'secrets' instance from config_manager
        self.config = secrets
        self.logger = structlog.get_logger().bind(component="database_updater")
        self.use_test_odoo = use_test_odoo
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self.secret_manager: Optional[SecretManagerClient] = None
        
        # Only instantiate SecretManagerClient if in production environment
        if self.config.ENVIRONMENT == 'production':
            if not self.config.GCP_PROJECT_ID:
                raise ValueError("GCP_PROJECT_ID is not set in production environment.")
            self.secret_manager = SecretManagerClient(self.config.GCP_PROJECT_ID)

        self.logger.info(
            "DatabaseUpdater initialized",
            environment=self.config.ENVIRONMENT,
            use_test_odoo=self.use_test_odoo
        )

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get database connection parameters from the central config."""
        try:
            db_config = self.config.get_database_config()
            # Ensure port is an integer
            db_config['port'] = int(db_config['port'])
            
            # Filter to only include valid PostgreSQL connection parameters
            valid_params = {
                'host', 'port', 'database', 'user', 'password', 'dbname',
                'connect_timeout', 'sslmode', 'sslcert', 'sslkey', 'sslrootcert',
                'sslcrl', 'application_name', 'fallback_application_name',
                'keepalives', 'keepalives_idle', 'keepalives_interval', 
                'keepalives_count', 'target_session_attrs', 'options'
            }
            
            # Only include parameters that are valid for psycopg2
            filtered_config = {k: v for k, v in db_config.items() if k in valid_params}
            
            self.logger.debug("Database connection parameters", 
                            host=filtered_config.get('host'), 
                            database=filtered_config.get('database'),
                            filtered_params=list(filtered_config.keys()))
            
            return filtered_config
        except (AttributeError, KeyError) as e:
            self.logger.error("Database configuration is missing or incomplete.", error=str(e))
            raise DatabaseConnectionError("Database configuration is incomplete.") from e

    def _setup_connection_pool(self):
        """Initialize the database connection pool."""
        if self._connection_pool:
            return
        try:
            params = self._get_connection_params()
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2, maxconn=10, **params, connect_timeout=30
            )
            self.logger.info(
                "Database connection pool created",
                host=params.get('host'), database=params.get('database')
            )
        except Exception as e:
            self.logger.error("Failed to create connection pool", error=str(e))
            raise DatabaseConnectionError("Failed to create connection pool.") from e

    @contextmanager
    def get_connection(self):
        """Context manager for getting a pooled database connection."""
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
    def get_latest_date_records(self) -> Tuple[Optional[date], set]:
        """Get the most recent date and existing records for anti-duplication."""
        with self.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT MAX(issuedDate) FROM sales_items WHERE issuedDate IS NOT NULL")
            latest_date = (result := cursor.fetchone()) and result[0]

            if not latest_date:
                self.logger.info("No existing records found.")
                return None, set()

            cursor.execute(
                "SELECT salesInvoiceId, items_product_sku FROM sales_items WHERE issuedDate = %s",
                (latest_date,)
            )
            existing_pairs = set(cursor.fetchall())
            self.logger.info(
                "Retrieved anti-duplication data",
                latest_date=str(latest_date),
                existing_pairs_count=len(existing_pairs)
            )
            return latest_date, existing_pairs

    def filter_duplicate_records(self, df: pd.DataFrame, existing_pairs: set) -> pd.DataFrame:
        """Filter out records that already exist for the latest date."""
        if not existing_pairs or df.empty:
            return df
            
        initial_count = len(df)
        # Use a more efficient method than apply/zip for creating composite keys
        composite_key = df['salesInvoiceId'].astype(str) + '|' + df['items_product_sku'].astype(str)
        mask = ~composite_key.isin({f"{inv}|{sku}" for inv, sku in existing_pairs})
        
        filtered_df = df[mask]
        duplicates_removed = initial_count - len(filtered_df)
        if duplicates_removed > 0:
            self.logger.info("Filtered duplicate records", duplicates_removed=duplicates_removed)
        return filtered_df

    def _clean_csv_value(self, value: Any) -> str:
        """Clean and escape values for PostgreSQL COPY."""
        if pd.isna(value):
            return r'\N'
        return str(value).replace('\\', r'\\').replace('\n', r'\n').replace('\r', r'\r').replace('\t', r'\t').replace('|', r'\|')

    @retry_on_db_error()
    def bulk_load_data(self, df: pd.DataFrame) -> int:
        """Efficiently load data using psycopg2.copy_from."""
        if df.empty:
            return 0

        columns = [
            'salesInvoiceId', 'doctype_name', 'docnumber', 'customer_customerid',
            'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
            'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
            'items_product_description', 'items_product_sku', 'items_quantity',
            'items_unitPrice', 'issuedDate', 'sales_channel'
        ]
        df_reordered = df.reindex(columns=columns)

        def data_iterator():
            for row in df_reordered.itertuples(index=False, name=None):
                yield '|'.join(self._clean_csv_value(field) for field in row) + '\n'

        with self.get_connection() as conn, conn.cursor() as cursor:
            self.logger.info("Starting bulk data load", record_count=len(df_reordered))
            cursor.copy_from(
                StringIteratorIO(data_iterator()),
                'sales_items', sep='|', null=r'\N', columns=columns
            )
            return cursor.rowcount

    def run_update(self, start_date_override: Optional[date] = None) -> UpdateResult:
        """Main orchestration method to run the complete update process."""
        run_start_time = datetime.now()
        self.logger.info("Database update process starting...")

        try:
            latest_date, existing_pairs = self.get_latest_date_records()

            start_date = start_date_override
            if start_date is None:
                start_date = (latest_date + pd.Timedelta(days=1)) if latest_date else (date.today() - pd.Timedelta(days=30))
            end_date = date.today()

            if start_date > end_date:
                self.logger.info("Database is already up-to-date.", latest_synced_date=str(latest_date))
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            self.logger.info("Fetching new sales data", start_date=str(start_date), end_date=str(end_date))

            # CORRECTED: Pass the use_test_odoo flag to the integration layer
            orders_df, lines_df = read_sales_by_date_range(start_date, end_date, use_test=self.use_test_odoo)

            if orders_df.empty:
                self.logger.info("No new sales data found in the specified date range.")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            combined_df = pd.merge(orders_df, lines_df, on='salesInvoiceId', how='inner')
            
            if latest_date and latest_date >= start_date:
                combined_df = self.filter_duplicate_records(combined_df, existing_pairs)

            if combined_df.empty:
                self.logger.info("No new records to insert after deduplication.")
                return UpdateResult(0, 0, run_start_time, datetime.now(), [])

            records_loaded = self.bulk_load_data(combined_df)
            self.logger.info("Database update completed successfully.", records_loaded=records_loaded)
            return UpdateResult(records_loaded, 0, run_start_time, datetime.now(), [])

        except Exception as e:
            self.logger.error("Database update failed.", error=str(e), exc_info=True)
            return UpdateResult(0, 1, run_start_time, datetime.now(), [str(e)])

    def close(self):
        """Clean up database connections and other resources."""
        try:
            if self._connection_pool:
                self._connection_pool.closeall()
                self.logger.info("Database connection pool closed.")
            cleanup_sales_provider()
        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point to run the database updater from the command line."""
    # Assuming setup_application_logging() is called from config_manager
    # or a main application entry point.
    main_logger = structlog.get_logger().bind(component="main")
    main_logger.info("Database updater application starting...")

    try:
        # Determine if we should use the test Odoo instance from environment
        use_test = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'

        with DatabaseUpdater(use_test_odoo=use_test) as updater:
            result = updater.run_update()
            main_logger.info(
                "Run complete.",
                status="SUCCESS" if not result.errors else "FAILURE",
                records_processed=result.total_processed,
                duration_sec=round(result.duration_seconds, 2),
                errors=result.errors
            )

    except Exception as e:
        main_logger.error("An unhandled exception occurred.", error=str(e), exc_info=True)
        exit(1)


if __name__ == "__main__":
    # In a real application, you might have a single entry point that
    # configures logging before calling this main function.
    main()
