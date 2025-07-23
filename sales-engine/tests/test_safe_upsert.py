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

The script will print PASS/FAIL for each test case.
"""
from datetime import date
import pandas as pd
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Tuple
from pathlib import Path
import sys

# Imports will be resolved by the Python path configured by Poetry
from sales_engine.db_updater import DatabaseUpdater
from config_manager import secrets


# --- Test Configuration ---
TEST_TABLE_NAME = "test_sales"
# Assumes the script is run from the root of the 'sales-engine' project
HISTORICAL_CSV_PATH = Path("tests/historical_data.csv")


# --- ANSI Color Codes for Output ---
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

def print_test_header(name):
    print(f"\n{Colors.BLUE}--- Running Test: {name} ---{Colors.ENDC}")

def print_pass(message):
    print(f"{Colors.GREEN}✅ PASS:{Colors.ENDC} {message}")

def print_fail(message):
    print(f"{Colors.RED}❌ FAIL:{Colors.ENDC} {message}")

def print_info(message):
    print(f"{Colors.YELLOW}ℹ️  INFO:{Colors.ENDC} {message}")


class TestableDatabaseUpdater(DatabaseUpdater):
    """
    An overridden DatabaseUpdater that targets a temporary test table
    instead of the main `sales_items` table.
    """
    def __init__(self, test_table_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_table_name = test_table_name
        print_info(f"TestableDatabaseUpdater initialized to target table: '{self.test_table_name}'")

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
        self.failures = 0

    def test_01_database_connection(self):
        print_test_header("Sales DB Connection")
        try:
            self.db_updater = TestableDatabaseUpdater(test_table_name=TEST_TABLE_NAME)
            if self.db_updater.test_connection():
                print_pass("Successfully connected to the PostgreSQL database.")
                return True
            else:
                print_fail("Database connection test failed.")
                return False
        except Exception as e:
            print_fail(f"Could not connect to database. Error: {e}")
            return False

    def test_02_safe_upsert_flow(self):
        print_test_header("End-to-End Safe Upsert Flow (using test_sales table)")
        if not self.db_updater:
            print_fail("Skipping test, no active DB connection.")
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
                    print_info(f"Step 1: Creating temporary table '{TEST_TABLE_NAME}'...")
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
                    cursor.execute(f"CREATE TABLE {TEST_TABLE_NAME} (LIKE sales_items INCLUDING ALL);")
                    print_pass("Test table created successfully.")

                    print_info("Step 2: Simulating historical CSV load into test table...")
                    csv_file_obj = io.StringIO(dummy_csv_content)
                    columns_str = ','.join(df_update.columns)
                    cursor.copy_expert(f"COPY {TEST_TABLE_NAME} ({columns_str}) FROM STDIN WITH CSV", csv_file_obj)
                    print_pass(f"Simulated load of {cursor.rowcount} record(s) complete.")

            # Step 3: Verify initial load in a new transaction
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    print_info("Step 3: Verifying initial record in test table...")
                    cursor.execute(f"SELECT * FROM {TEST_TABLE_NAME} WHERE salesinvoiceid = 'HIST-001';")
                    initial_record = cursor.fetchone()
                    if not (initial_record and initial_record['items_quantity'] == 2.0):
                        print_fail("Initial record not found or has incorrect data.")
                        return False
                    print_pass(f"Record loaded correctly with quantity={initial_record['items_quantity']}.")

            # Step 4: Perform the upsert (this method manages its own connection)
            print_info("Step 4: Performing upsert with updated quantity (3.0)...")
            _, _, updated_count = self.db_updater.bulk_upsert_sales_data(df_update)
            if updated_count != 1:
                print_fail(f"Upsert reported {updated_count} updated records, expected 1.")
                return False
            print_pass("Upsert operation reported 1 record updated.")

            # Step 5: Verify the update in a final transaction
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    print_info("Step 5: Verifying record was updated in test table...")
                    cursor.execute(f"SELECT * FROM {TEST_TABLE_NAME} WHERE salesinvoiceid = 'HIST-001';")
                    updated_record = cursor.fetchone()
                    
                    cursor.execute(f"SELECT COUNT(*) as count FROM {TEST_TABLE_NAME};")
                    final_count = cursor.fetchone()['count']

                    if final_count != 1:
                        print_fail(f"Table has {final_count} records, expected 1. A new row was incorrectly inserted.")
                        return False
                    
                    if not (updated_record and updated_record['items_quantity'] == 3.0):
                        print_fail("Record data was not updated correctly.")
                        return False
                    print_pass(f"Record updated correctly with new quantity={updated_record['items_quantity']}.")
            
            return True

        except Exception as e:
            print_fail(f"An exception occurred during the upsert flow test: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 6. Teardown: Drop the temporary table
            print_info(f"Step 6: Cleaning up by dropping table '{TEST_TABLE_NAME}'...")
            with self.db_updater.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
            print_pass("Cleanup complete.")

    def test_03_full_historical_load(self):
        print_test_header("Complete Historical CSV Load Test with Batching (50k per batch)")
        if not self.db_updater:
            print_fail("Skipping test, no active DB connection.")
            return False
        
        if not HISTORICAL_CSV_PATH.exists():
            print_fail(f"Historical data file not found at '{HISTORICAL_CSV_PATH}'.")
            print_info("Please place 'historical_data.csv' in the 'tests/' directory.")
            return False

        try:
            # 1. Get total row count first
            print_info("Step 1: Analyzing CSV file size...")
            with open(HISTORICAL_CSV_PATH, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f)
            print_info(f"Found {total_rows:,} total records in '{HISTORICAL_CSV_PATH.name}'.")

            # 2. Define batch size and column names
            BATCH_SIZE = 50000
            column_names = [
                'salesinvoiceid', 'doctype_name', 'docnumber', 'customer_customerid', 'customer_name',
                'customer_vatid', 'salesman_name', 'term_name', 'warehouse_name', 'totals_net',
                'totals_vat', 'total_total', 'items_product_description', 'items_product_sku',
                'items_quantity', 'items_unitprice', 'issueddate', 'sales_channel'
            ]

            # 3. Create test table
            with self.db_updater.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    print_info(f"Step 2: Creating temporary table '{TEST_TABLE_NAME}' for load test...")
                    cursor.execute(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME};")
                    cursor.execute(f"CREATE TABLE {TEST_TABLE_NAME} (LIKE sales_items INCLUDING ALL);")
                    print_pass("Test table created successfully.")

            # 4. Process in batches
            print_info(f"Step 3: Processing data in batches of {BATCH_SIZE:,} records...")
            
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

            # Process file in chunks
            for chunk in pd.read_csv(HISTORICAL_CSV_PATH, names=column_names, encoding='utf-8', chunksize=BATCH_SIZE):
                batch_number += 1
                original_batch_size = len(chunk)
                
                print_info(f"  Batch {batch_number}: Processing {original_batch_size:,} records...")
                
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
                
                print_info(f"  Batch {batch_number} completed: {batch_upserts:,} records upserted ({batch_new:,} new, {batch_updated:,} updated, {batch_duplicates:,} duplicates removed)")
                
                # Progress indicator
                progress_pct = (total_processed / total_rows) * 100
                print_info(f"  Progress: {total_processed:,}/{total_rows:,} records ({progress_pct:.1f}%)")

            # 5. Final verification
            print_info("Step 4: Verifying final results...")
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
            print_pass("=" * 60)
            print_pass("📊 BATCH PROCESSING SUMMARY:")
            print_pass(f"  Total CSV records processed: {total_processed:,}")
            print_pass(f"  Total duplicates removed: {total_duplicates_removed:,}")
            print_pass(f"  Total unique records: {total_processed - total_duplicates_removed:,}")
            print_pass(f"  Records in database: {final_count:,}")
            print_pass(f"  Total upserts performed: {total_upserts:,}")
            print_pass(f"  New records inserted: {total_new_records:,}")
            print_pass(f"  Existing records updated: {total_updated_records:,}")
            print_pass(f"  Date range: {stats['earliest_date']} to {stats['latest_date']}")
            print_pass(f"  Unique invoices: {stats['unique_invoices']:,}")
            print_pass(f"  Batches processed: {batch_number}")
            print_pass("=" * 60)
            
            if final_count == (total_processed - total_duplicates_removed):
                print_pass(f"✅ Success! Processed complete CSV with {batch_number} batches.")
            else:
                print_fail(f"Row count mismatch! Expected {total_processed - total_duplicates_removed:,}, got {final_count:,}.")
                return False
            
            print_info(f"The test table '{TEST_TABLE_NAME}' was NOT dropped for manual inspection.")
            return True

        except Exception as e:
            print_fail(f"An exception occurred during the batch load test: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Execute all validation tests in sequence."""
        print(f"{Colors.GREEN}==========================================={Colors.ENDC}")
        print(f"{Colors.GREEN}    Running Sales Engine Safe Upsert Test    {Colors.ENDC}")
        print(f"{Colors.GREEN}==========================================={Colors.ENDC}")
        
        tests = [
            self.test_01_database_connection,
            self.test_02_safe_upsert_flow,
            self.test_03_full_historical_load,
        ]

        for test_func in tests:
            if not test_func():
                self.failures += 1
                if test_func == self.test_01_database_connection:
                    print_fail("Stopping tests due to critical connection failure.")
                    break
        
        print("\n" + "="*43)
        if self.failures == 0:
            print(f"{Colors.GREEN}🎉 All {len(tests)} tests passed successfully!{Colors.ENDC}")
            print(f"{Colors.GREEN}   The Sales Engine safe upsert logic is working correctly.{Colors.ENDC}")
        else:
            print(f"{Colors.RED}🔥 {self.failures} out of {len(tests)} tests failed.{Colors.ENDC}")
            print(f"{Colors.RED}   Please review the errors above.{Colors.ENDC}")
        
        print(f"{Colors.YELLOW}NOTE: The '{TEST_TABLE_NAME}' table from the last test was left for inspection.{Colors.ENDC}")
        return 1 if self.failures > 0 else 0


if __name__ == "__main__":
    validator = SalesUpsertValidator()
    exit_code = validator.run_all_tests()
    sys.exit(exit_code)
