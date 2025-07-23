# odoo-api/src/odoo_api/run_refactor_tests.py
"""
Refactor Validation Test Module for OdooSales

This script provides a simple, framework-free way to test the refactored
OdooSales class. It connects to a live Odoo instance and runs a series of
checks to ensure the data fetching and processing logic works as expected.

Usage:
    - Place this file inside the 'odoo_api' source directory.
    - Run from the parent directory (e.g., 'odoo-api/'):
      python -m src.odoo_api.run_refactor_tests

The script will print PASS/FAIL for each test case.
"""
import os
import sys
from datetime import datetime, date, timedelta
import pandas as pd

# This allows the script to import from the parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from odoo_api.sales import OdooSales
    from config_manager import secrets
except ImportError as e:
    print(f"❌ FATAL: Could not import necessary modules. Ensure this script is run correctly.")
    print(f"   Error: {e}")
    print(f"   Usage: python -m src.odoo_api.run_refactor_tests")
    sys.exit(1)


# --- Test Configuration ---
# We will test a small, recent date range to keep tests fast.
TEST_END_DATE = date.today()
TEST_START_DATE = TEST_END_DATE - timedelta(days=7)
TEST_LIMIT = 25 # Limit the number of orders to speed up the test

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


class RefactorValidator:
    """A simple test runner for the OdooSales refactor."""

    def __init__(self):
        self.sales_api = None
        self.test_data = None # To store fetched data and avoid re-fetching
        self.failures = 0

    def test_01_odoo_connection(self):
        print_test_header("Odoo API Connection")
        try:
            # Use the test credentials if available, otherwise production
            use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
            odoo_config = secrets.get_odoo_config(use_test=use_test_odoo)
            
            self.sales_api = OdooSales(
                db=odoo_config['db'],
                url=odoo_config['url'],
                username=odoo_config['username'],
                password=odoo_config['password']
            )
            if self.sales_api.uid:
                print_pass(f"Successfully connected to Odoo server at {odoo_config['url']}")
                print_info(f"Connected as user ID: {self.sales_api.uid}")
                return True
            else:
                print_fail("Connection established but failed to get a user ID (UID).")
                return False
        except Exception as e:
            print_fail(f"Could not connect to Odoo. Error: {e}")
            return False

    def test_02_fetch_data(self):
        print_test_header("Fetch Sales Data for Recent Week")
        if not self.sales_api:
            print_fail("Skipping test, no active Odoo connection.")
            return False

        try:
            print_info(f"Fetching sales data from {TEST_START_DATE} to {TEST_END_DATE} (limit={TEST_LIMIT})...")
            self.test_data = self.sales_api.read_sales_by_date_range(
                start_date=TEST_START_DATE,
                end_date=TEST_END_DATE,
                limit=TEST_LIMIT
            )

            if isinstance(self.test_data, pd.DataFrame):
                print_pass(f"API call successful. Returned a pandas DataFrame.")
                print_info(f"Fetched {len(self.test_data)} combined order line items.")
                print_info(f"data.info(): {self.test_data.info()}")
                # It's okay if no data is found, the API should just return an empty frame
                if self.test_data.empty:
                    print_info("The returned DataFrame is empty, which is a valid result if no sales occurred.")
                return True
            else:
                print_fail(f"The method did not return a DataFrame. Got type: {type(self.test_data)}")
                return False
        except Exception as e:
            print_fail(f"An exception occurred during data fetching: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_03_dataframe_structure(self):
        print_test_header("DataFrame Structure and Columns")
        if self.test_data is None:
            print_fail("Skipping test, no data was fetched.")
            return False
        
        if self.test_data.empty:
            print_pass("DataFrame is empty, skipping structure validation.")
            return True

        expected_columns = [
            'salesinvoiceid', 'doctype_name', 'docnumber', 'customer_customerid',
            'customer_name', 'customer_vatid', 'salesman_name', 'term_name',
            'warehouse_name', 'totals_net', 'totals_vat', 'total_total',
            'items_product_description', 'items_product_sku', 'items_quantity',
            'items_unitprice', 'issueddate', 'sales_channel'
        ]

        missing_cols = [col for col in expected_columns if col not in self.test_data.columns]
        extra_cols = [col for col in self.test_data.columns if col not in expected_columns]

        if not missing_cols and not extra_cols:
            print_pass("DataFrame has the exact 18 columns required.")
        else:
            if missing_cols:
                print_fail(f"DataFrame is missing required columns: {missing_cols}")
            if extra_cols:
                print_fail(f"DataFrame has unexpected extra columns: {extra_cols}")
            return False
        
        return True

    def test_04_data_types_and_nulls(self):
        print_test_header("Data Types and Null Primary Keys")
        if self.test_data is None or self.test_data.empty:
            print_pass("Skipping test, no data to validate.")
            return True

        # 1. Check for nulls in primary key columns
        pk_nulls = self.test_data[['salesinvoiceid', 'items_product_sku']].isnull().sum()
        if pk_nulls.sum() == 0:
            print_pass("No null values found in primary key columns (salesinvoiceid, items_product_sku).")
        else:
            print_fail(f"Found null values in primary key columns:\n{pk_nulls}")
            return False

        # 2. Check data types for key columns
        try:
            # This will raise an error if conversion fails
            pd.to_datetime(self.test_data['issueddate'])
            print_pass("'issueddate' column is in a valid date format.")
            
            numeric_cols = ['totals_net', 'totals_vat', 'total_total', 'items_quantity', 'items_unitprice']
            for col in numeric_cols:
                if not pd.api.types.is_numeric_dtype(self.test_data[col]):
                     print_fail(f"Column '{col}' is not a numeric type. Found {self.test_data[col].dtype}.")
                     return False
            print_pass("All key numeric columns have correct data types.")

        except Exception as e:
            print_fail(f"Data type validation failed. Error: {e}")
            return False
            
        return True

    def test_05_data_logic(self):
        print_test_header("Data Logical Consistency")
        if self.test_data is None or self.test_data.empty:
            print_pass("Skipping test, no data to validate.")
            return True

        # Check if totals add up (allowing for small rounding differences)
        total_check = abs(self.test_data['totals_net'] + self.test_data['totals_vat'] - self.test_data['total_total']) < 0.02
        if total_check.all():
            print_pass("Financial totals are consistent (net + vat ≈ total).")
        else:
            mismatches = self.test_data[~total_check]
            print_fail(f"Found {len(mismatches)} rows where net + vat != total.")
            print_info("Showing first 3 mismatches:")
            print(mismatches[['salesinvoiceid', 'totals_net', 'totals_vat', 'total_total']].head(3))
            return False
        
        return True

    def run_all_tests(self):
        """Execute all validation tests in sequence."""
        print(f"{Colors.GREEN}==========================================={Colors.ENDC}")
        print(f"{Colors.GREEN}  Running OdooSales Refactor Validation  {Colors.ENDC}")
        print(f"{Colors.GREEN}==========================================={Colors.ENDC}")
        
        tests = [
            self.test_01_odoo_connection,
            self.test_02_fetch_data,
            self.test_03_dataframe_structure,
            self.test_04_data_types_and_nulls,
            self.test_05_data_logic,
        ]

        for test_func in tests:
            if not test_func():
                self.failures += 1
        
        print("\n" + "="*43)
        if self.failures == 0:
            print(f"{Colors.GREEN}🎉 All {len(tests)} tests passed successfully!{Colors.ENDC}")
            print(f"{Colors.GREEN}   The refactored OdooSales class appears to be working correctly.{Colors.ENDC}")
            return 0
        else:
            print(f"{Colors.RED}🔥 {self.failures} out of {len(tests)} tests failed.{Colors.ENDC}")
            print(f"{Colors.RED}   Please review the errors above.{Colors.ENDC}")
            return 1


if __name__ == "__main__":
    validator = RefactorValidator()
    exit_code = validator.run_all_tests()
    sys.exit(exit_code)