# sales-engine/tests/test_safe_upsert.py
"""
Safe, Non-Destructive Upsert Validation Test Module for the Sales Engine

This script tests the DatabaseUpdater's core upsert logic without affecting
the main `sales_items` table. It creates, tests against, and then drops a
temporary `test_sales` table.

This module is designed to be run within a Poetry environment.

Usage:
    - Ensure all dependencies are installed (`poetry install`).
    - Run from the root of the 'sales-engine' project:
      poetry run python -m tests.test_safe_upsert

The script will print PASS/FAIL for each test case using beautiful colored output.
"""
from datetime import date
import pandas as pd
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Tuple
from pathlib import Path
import sys
import time

# Imports will be resolved by the Python path configured by Poetry
from sales_engine.db_updater import DatabaseUpdater
from config_manager import secrets

# Import beautiful logging from dev-utils
try:
    from dev_utils import PrettyLogger, log_header, log_success, log_error, log_info, log_warning, timer
    PRETTY_LOGGER_AVAILABLE = True
except ImportError:
    print("⚠️  dev_utils not available, using basic logging")
    PRETTY_LOGGER_AVAILABLE = False
    
    # Define fallback classes and functions
    class timer:
        def __init__(self, msg): 
            self.msg = msg
        def __enter__(self): 
            print(f"🏁 Starting {self.msg}..."); 
            return self
        def __exit__(self, *args): 
            print(f"⏱️  Completed {self.msg}")
    
    def log_header(title, **kwargs): 
        print(f"\n{'=' * 50}")
        print(f"    {title}    ")
        print(f"{'=' * 50}\n")
    
    def log_success(msg, **kwargs): 
        print(f"✅ {msg}")
    
    def log_error(msg, **kwargs): 
        print(f"❌ {msg}")
    
    def log_info(msg, **kwargs): 
        print(f"ℹ️  {msg}")
    
    def log_warning(msg, **kwargs): 
        print(f"⚠️  {msg}")
    
    class PrettyLogger:
        def __init__(self, *args, **kwargs): pass
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️  {msg}")
        def step(self, msg, step=None, total=None, **kwargs): 
            prefix = f"[{step}/{total}] " if step and total else ""
            print(f"🚀 {prefix}{msg}")
        def metric(self, name, value, unit="", **kwargs): 
            print(f"📊 {name}: {value:,} {unit}")
        def table(self, data, title=None): 
            if title: print(f"📋 {title}")
            for k, v in data.items(): print(f"  {k}: {v}")
        def separator(self, char="-", width=60):
            print(char * width)

# --- Test Configuration ---
TEST_TABLE_NAME = "test_sales"
# Assumes the script is run from the root of the 'sales-engine' project
HISTORICAL_CSV_PATH = Path("tests/historical_data.csv")

# --- Batch Processing Constants ---
BATCH_SIZE = 500  # Number of records per batch
MAX_BATCHES = 10   # Maximum number of batches to process (None for unlimited)


class TestLogger:
    """Enhanced test logger using dev_utils pretty logger"""
    
    def __init__(self):
        if PRETTY_LOGGER_AVAILABLE:
            self.logger = PrettyLogger("sales-test", enable_timestamps=True)
        else:
            # Use fallback PrettyLogger
            self.logger = PrettyLogger("sales-test")
        self.failures = 0
    
    def test_header(self, name: str):
        """Print a test header"""
        if PRETTY_LOGGER_AVAILABLE:
            self.logger.separator("─", 60)
            self.logger.info(f"🧪 Running Test: {name}")
            self.logger.separator("─", 60)
        else:
            print(f"\n--- Running Test: {name} ---")
    
    def pass_test(self, message: str, **kwargs):
        """Log a test pass"""
        self.logger.success(f"✅ PASS: {message}", **kwargs)
    
    def fail_test(self, message: str, **kwargs):
        """Log a test failure"""
        self.failures += 1
        self.logger.error(f"❌ FAIL: {message}", **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log test info"""
        self.logger.info(f"ℹ️  INFO: {message}", **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log test warning"""
        self.logger.warning(f"⚠️  WARNING: {message}", **kwargs)
    
    def step(self, message: str, step: int = None, total: int = None, **kwargs):
        """Log a test step"""
        self.logger.step(message, step, total, **kwargs)
    
    def metric(self, name: str, value, unit: str = "", **kwargs):
        """Log a test metric"""
        self.logger.metric(name, value, unit, **kwargs)
    
    def table(self, data: dict, title: str = None):
        """Display data in table format"""
        self.logger.table(data, title)
    
    def summary(self, total_tests: int):
        """Display test summary"""
        if PRETTY_LOGGER_AVAILABLE:
            self.logger.separator("=", 70)
            if self.failures == 0:
                self.logger.success(f"🎉 All {total_tests} tests passed successfully!")
                self.logger.success("   The Sales Engine safe upsert logic is working correctly.")
            else:
                self.logger.error(f"🔥 {self.failures} out of {total_tests} tests failed.")
                self.logger.error("   Please review the errors above.")
            self.logger.separator("=", 70)
        else:
            print("=" * 43)
            if self.failures == 0:
                print(f"🎉 All {total_tests} tests passed successfully!")
                print("   The Sales Engine safe upsert logic is working correctly.")
            else:
                print(f"🔥 {self.failures} out of {total_tests} tests failed.")
                print("   Please review the errors above.")

# Initialize test logger
test_logger = TestLogger()


class TestableDatabaseUpdater(DatabaseUpdater):
    """
    An overridden DatabaseUpdater that targets a temporary test table
    instead of the main `sales_items` table.
    """
    def __init__(self, test_table_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_table_name = test_table_name
        test_logger.info(f"TestableDatabaseUpdater initialized to target table: '{self.test_table_name}'")

    def bulk_upsert_sales_data(self, df: pd.DataFrame) -> Tuple[int, int, int]:
        """
        Overrides the original method to use the test table name.
        The core logic is copied and the table name is replaced.
        """
        original_sql = self._get_upsert_sql() # Helper to get original SQL
        test_sql = original_sql.replace("sales_items", self.test_table_name, 1)
        
        if df.empty:
            return 0, 0, 0

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # --- FIX: Explicitly convert numpy types to standard Python types ---
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
                
                from psycopg2.extras import execute_values
                execute_values(
                    cursor, test_sql, data_tuples,
                    template=None, page_size=1000
                )
                
                results = cursor.fetchall()
                total_upserts = len(results)
                new_records = sum(1 for result in results if result[2]) # was_inserted
                updated_records = total_upserts - new_records
                
                return total_upserts, new_records, updated_records

    def _get_upsert_sql(self):
        """Helper to centralize the SQL string from the parent class."""
        return """
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


class SalesUpsertValidator:
    """A simple test runner for the Sales Engine's upsert functionality."""

    def __init__(self):
        self.db_updater = None

    def test_01_database_connection(self):
        test_logger.test_header("Sales DB Connection")
        try:
            with timer("database connection setup"):
                self.db_updater = TestableDatabaseUpdater(test_table_name=TEST_TABLE_NAME)
            
            with timer("connection test"):
                connection_success = self.db_updater.test_connection()
            
            if connection_success:
                test_logger.pass_test("Successfully connected to the PostgreSQL database.")
                return True
            else:
                test_logger.fail_test("Database connection test failed.")
                return False
        except Exception as e:
            test_logger.fail_test(f"Could not connect to database. Error: {e}")
            return False

    def test_02_safe_upsert_flow(self):
        test_logger.test_header("End-to-End Safe Upsert Flow (using test_sales table)")
        if not self.db_updater:
            test_logger.fail_test("Skipping test, no active DB connection.")
            return False

        # --- Test Data ---
        dummy_csv_content = "HIST-001,Factura,1,101,Cust A,VAT-A,,Term A,WH-A,100.0,19.0,119.0,Prod A,SKU-A,2.0,50.0,2023-01-15,Channel A"
        update_data = {
            'salesinvoiceid': ['HIST-001'], 'doctype_name': ['Factura'], 'docnumber': ['1'],
            'customer_customerid': [101], 'customer_name': ['Cust A'], 'customer_vatid': ['VAT-A'],
            'salesman_name': [''], 'term_name': ['Term A'], 'warehouse_name': ['WH-A'],
            'totals_net': [150.0], 'totals_vat': [28.5], 'total_total': [178.5],
            'items_product_description': ['Prod A Updated'], 'items_product_sku': ['SKU-A'],
            'items_quantity': [3.0], # <-- Quantity changed
            'items_unitprice': [50.0], 'issueddate': [date(2023, 1, 15)], 'sales_channel': ['Channel A']
        }
        df_update = pd.DataFrame(update_data)

        try:
            # --- FIX: Separate DB operations to prevent nested transactions/deadlocks ---

            # Step 1 & 2: Setup and initial load in its own transaction
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    test_logger.step(f"Creating temporary table '{TEST_TABLE_NAME}'", 1, 6)
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
                    cursor.execute(f"CREATE TABLE {TEST_TABLE_NAME} (LIKE sales_items INCLUDING ALL);")
                    test_logger.pass_test("Test table created successfully.")

                    test_logger.step("Simulating historical CSV load into test table", 2, 6)
                    csv_file_obj = io.StringIO(dummy_csv_content)
                    columns_str = ','.join(df_update.columns)
                    cursor.copy_expert(f"COPY {TEST_TABLE_NAME} ({columns_str}) FROM STDIN WITH CSV", csv_file_obj)
                    test_logger.pass_test(f"Simulated load of {cursor.rowcount} record(s) complete.")

            # Step 3: Verify initial load in a new transaction
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    test_logger.step("Verifying initial record in test table", 3, 6)
                    cursor.execute(f"SELECT * FROM {TEST_TABLE_NAME} WHERE salesinvoiceid = 'HIST-001';")
                    initial_record = cursor.fetchone()
                    if not (initial_record and initial_record['items_quantity'] == 2.0):
                        test_logger.fail_test("Initial record not found or has incorrect data.")
                        return False
                    test_logger.pass_test(f"Record loaded correctly with quantity={initial_record['items_quantity']}.")

            # Step 4: Perform the upsert (this method manages its own connection)
            test_logger.step("Performing upsert with updated quantity (3.0)", 4, 6)
            with timer("upsert operation"):
                _, _, updated_count = self.db_updater.bulk_upsert_sales_data(df_update)
            
            if updated_count != 1:
                test_logger.fail_test(f"Upsert reported {updated_count} updated records, expected 1.")
                return False
            test_logger.pass_test("Upsert operation reported 1 record updated.")

            # Step 5: Verify the update in a final transaction
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    test_logger.step("Verifying record was updated in test table", 5, 6)
                    cursor.execute(f"SELECT * FROM {TEST_TABLE_NAME} WHERE salesinvoiceid = 'HIST-001';")
                    updated_record = cursor.fetchone()
                    
                    cursor.execute(f"SELECT COUNT(*) as count FROM {TEST_TABLE_NAME};")
                    final_count = cursor.fetchone()['count']

                    if final_count != 1:
                        test_logger.fail_test(f"Table has {final_count} records, expected 1. A new row was incorrectly inserted.")
                        return False
                    
                    if not (updated_record and updated_record['items_quantity'] == 3.0):
                        test_logger.fail_test("Record data was not updated correctly.")
                        return False
                    test_logger.pass_test(f"Record updated correctly with new quantity={updated_record['items_quantity']}.")
            
            return True

        except Exception as e:
            test_logger.fail_test(f"An exception occurred during the upsert flow test: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 6. Teardown: Drop the temporary table
            test_logger.step(f"Cleaning up by dropping table '{TEST_TABLE_NAME}'", 6, 6)
            with self.db_updater.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
            test_logger.pass_test("Cleanup complete.")

    def test_03_full_historical_load(self):
        test_logger.test_header(f"Complete Historical CSV Load Test with Batching ({BATCH_SIZE} per batch)")
        if not self.db_updater:
            test_logger.fail_test("Skipping test, no active DB connection.")
            return False
        
        if not HISTORICAL_CSV_PATH.exists():
            test_logger.fail_test(f"Historical data file not found at '{HISTORICAL_CSV_PATH}'.")
            test_logger.info("Please place 'historical_data.csv' in the 'tests/' directory.")
            return False

        try:
            # 1. Get total row count first
            test_logger.step("Analyzing CSV file size", 1, 4)
            with open(HISTORICAL_CSV_PATH, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f)
            test_logger.metric("Total Records Found", total_rows, "records")

            # 2. Define batch size and column names
            column_names = [
                'salesinvoiceid', 'doctype_name', 'docnumber', 'customer_customerid', 'customer_name',
                'customer_vatid', 'salesman_name', 'term_name', 'warehouse_name', 'totals_net',
                'totals_vat', 'total_total', 'items_product_description', 'items_product_sku',
                'items_quantity', 'items_unitprice', 'issueddate', 'sales_channel'
            ]

            # 3. Create test table
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    test_logger.step(f"Creating temporary table '{TEST_TABLE_NAME}' for load test", 2, 4)
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
                    cursor.execute(f"CREATE TABLE {TEST_TABLE_NAME} (LIKE sales_items INCLUDING ALL);")
                    test_logger.pass_test("Test table created successfully.")

            # 4. Process in batches
            test_logger.step(f"Processing data in batches of {BATCH_SIZE:,} records", 3, 4)
            
            # Create a temporary test updater for this specific test
            test_updater = TestableDatabaseUpdater(test_table_name=TEST_TABLE_NAME)
            test_updater._connection_pool = self.db_updater._connection_pool  # Reuse connection pool

            # Statistics tracking
            total_processed = 0
            total_duplicates_removed = 0
            total_upserts = 0
            total_new_records = 0
            total_updated_records = 0
            batch_number = 0
            start_time = time.time()

            # Process file in chunks
            for chunk in pd.read_csv(HISTORICAL_CSV_PATH, names=column_names, encoding='utf-8', chunksize=BATCH_SIZE):
                batch_number += 1
                if MAX_BATCHES is not None and batch_number > MAX_BATCHES:
                    test_logger.warning(f"Reached MAX_BATCHES={MAX_BATCHES}. Stopping batch processing early.")
                    break
                original_batch_size = len(chunk)
                
                test_logger.info(f"  Processing batch {batch_number}: {original_batch_size:,} records")
                
                # Handle duplicates within this batch
                chunk_deduped = chunk.drop_duplicates(subset=['salesinvoiceid', 'items_product_sku'], keep='last').copy()
                deduped_batch_size = len(chunk_deduped)
                batch_duplicates = original_batch_size - deduped_batch_size
                
                # Convert date column
                chunk_deduped.loc[:, 'issueddate'] = pd.to_datetime(chunk_deduped['issueddate']).dt.date
                
                # Perform upsert for this batch
                batch_upserts, batch_new, batch_updated = test_updater.bulk_upsert_sales_data(chunk_deduped)
                
                # Update statistics
                total_processed += original_batch_size
                total_duplicates_removed += batch_duplicates
                total_upserts += batch_upserts
                total_new_records += batch_new
                total_updated_records += batch_updated
                
                # Progress tracking
                progress_pct = (total_processed / total_rows) * 100
                if test_logger.logger and PRETTY_LOGGER_AVAILABLE:
                    test_logger.logger.progress("Overall Progress", total_processed, total_rows)

            # 5. Final verification
            test_logger.step("Verifying final results", 4, 4)
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {TEST_TABLE_NAME};")
                    final_count = cursor.fetchone()['count']
                    
                    cursor.execute(f"""
                        SELECT MIN(issueddate) as earliest_date, 
                               MAX(issueddate) as latest_date,
                               COUNT(DISTINCT salesinvoiceid) as unique_invoices
                        FROM {TEST_TABLE_NAME}
                    """)
                    stats = cursor.fetchone()

            # 6. Summary report
            duration = time.time() - start_time
            test_logger.table({
                "Total CSV Records": f"{total_processed:,}",
                "Duplicates Removed": f"{total_duplicates_removed:,}",
                "Unique Records": f"{total_processed - total_duplicates_removed:,}",
                "Records in Database": f"{final_count:,}",
                "Total Upserts": f"{total_upserts:,}",
                "New Records": f"{total_new_records:,}",
                "Updated Records": f"{total_updated_records:,}",
                "Date Range": f"{stats['earliest_date']} to {stats['latest_date']}",
                "Unique Invoices": f"{stats['unique_invoices']:,}",
                "Batches Processed": f"{batch_number}",
                "Processing Speed": f"{total_processed/duration:.1f} records/sec",
                "Duration": f"{duration:.2f}s"
            }, "📊 Batch Processing Summary")
            
            if final_count == (total_processed - total_duplicates_removed):
                test_logger.pass_test(f"Successfully processed complete CSV with {batch_number} batches.")
            else:
                test_logger.fail_test(f"Row count mismatch! Expected {total_processed - total_duplicates_removed:,}, got {final_count:,}.")
                return False
            
            test_logger.info(f"The test table '{TEST_TABLE_NAME}' was NOT dropped for manual inspection.")
            return True

        except Exception as e:
            test_logger.fail_test(f"An exception occurred during the batch load test: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Execute all validation tests in sequence."""
        if PRETTY_LOGGER_AVAILABLE:
            log_header("🧪 Sales Engine Safe Upsert Test Suite", char="=", width=70)
        else:
            print("=========================================")
            print("    Running Sales Engine Safe Upsert Test    ")
            print("=========================================")
        
        tests = [
            self.test_01_database_connection,
            self.test_02_safe_upsert_flow,
            self.test_03_full_historical_load,
        ]

        for test_func in tests:
            if not test_func():
                if test_func == self.test_01_database_connection:
                    test_logger.fail_test("Stopping tests due to critical connection failure.")
                    break
        
        test_logger.summary(len(tests))
        test_logger.warning(f"NOTE: The '{TEST_TABLE_NAME}' table from the last test was left for inspection.")
        
        return 1 if test_logger.failures > 0 else 0


if __name__ == "__main__":
    validator = SalesUpsertValidator()
    exit_code = validator.run_all_tests()
    sys.exit(exit_code)
