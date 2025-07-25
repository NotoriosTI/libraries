"""
One-time script to load historical sales data from a headerless CSV file
into the sales_items table after schema refactoring.

This script handles:
- Headerless CSV files
- Duplicate record handling (keeps most recent)
- Efficient bulk loading using upsert operations
- Proper column mapping to database schema
- Error handling and progress reporting

Usage:
    python load_historical_data.py [csv_file_path]

Example:
    python load_historical_data.py historic_sales.csv
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import pandas as pd
from typing import Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

# Import the centralized configuration
from config_manager import secrets

# --- ANSI Color Codes for Output ---
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'

def print_info(message):
    print(f"{Colors.CYAN}ℹ️  INFO:{Colors.ENDC} {message}")

def print_success(message):
    print(f"{Colors.GREEN}✅ SUCCESS:{Colors.ENDC} {message}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠️  WARNING:{Colors.ENDC} {message}")

def print_error(message):
    print(f"{Colors.RED}❌ ERROR:{Colors.ENDC} {message}")

def print_progress(message):
    print(f"{Colors.PURPLE}📊 PROGRESS:{Colors.ENDC} {message}")

def print_batch(message):
    print(f"{Colors.BLUE}🔄 BATCH:{Colors.ENDC} {message}")


class HistoricalDataLoader:
    """Loads historical sales data from headerless CSV files with duplicate handling."""
    
    def __init__(self):
        """Initialize the loader with database configuration."""
        self.db_config = secrets.get_database_config()
        
        # Column mapping for the 18 columns in the CSV (in order)
        # Based on sample: F00004281,Factura,4281,11265,MARIA A. OLMOS S.,8.337.898-0,,CHEQUE AL DIA,TIENDA,66245.0,12587.0,78832.0,Aceite Esencial Sandalo 10ML,7425,1.0,5966.39,2016-06-09,Tienda Sabaj
        self.csv_columns = [
            'salesinvoiceid',           # F00004281
            'doctype_name',             # Factura  
            'docnumber',                # 4281
            'customer_customerid',      # 11265
            'customer_name',            # MARIA A. OLMOS S.
            'customer_vatid',           # 8.337.898-0
            'salesman_name',            # (empty in sample)
            'term_name',                # CHEQUE AL DIA
            'warehouse_name',           # TIENDA
            'totals_net',               # 66245.0
            'totals_vat',               # 12587.0
            'total_total',              # 78832.0
            'items_product_description', # Aceite Esencial Sandalo 10ML
            'items_product_sku',        # 7425
            'items_quantity',           # 1.0
            'items_unitprice',          # 5966.39
            'issueddate',               # 2016-06-09
            'sales_channel'             # Tienda Sabaj
        ]
        
        print_info(f"HistoricalDataLoader initialized for database '{self.db_config.get('database', 'salesdb')}' with {len(self.csv_columns)} columns")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=int(self.db_config['port']),
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                cursor_factory=RealDictCursor
            )
            yield conn
            conn.commit()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print_error(f"Database transaction failed: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            print_error(f"Failed to connect to database: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def validate_csv_file(self, csv_file_path: Path) -> bool:
        """Validate that the CSV file exists and is readable."""
        if not csv_file_path.exists():
            print_error(f"CSV file does not exist: {csv_file_path}")
            return False
        
        if not csv_file_path.is_file():
            print_error(f"Path is not a file: {csv_file_path}")
            return False
        
        try:
            # Check if file is readable and estimate row count
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    print_error("CSV file appears to be empty")
                    return False
                
                # Count columns in first line
                column_count = len(first_line.split(','))
                if column_count != len(self.csv_columns):
                    print_warning(f"Column count mismatch: expected {len(self.csv_columns)}, found {column_count}")
                    print_warning(f"First line preview: {first_line[:100]}{'...' if len(first_line) > 100 else ''}")
                
                # Estimate total rows (for progress reporting)
                f.seek(0)
                estimated_rows = sum(1 for _ in f)
                
            print_success(f"CSV file validated: {csv_file_path} ({estimated_rows:,} rows, {column_count} columns)")
            return True
            
        except Exception as e:
            print_error(f"Failed to validate CSV file {csv_file_path}: {e}")
            return False

    def bulk_upsert_sales_data(self, df: pd.DataFrame) -> Tuple[int, int, int]:
        """
        Perform bulk upsert using INSERT ... ON CONFLICT DO UPDATE SET.
        Returns (total_upserts, new_records, updated_records)
        """
        if df.empty:
            return 0, 0, 0

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                
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

                # Convert data to tuples
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

                execute_values(
                    cursor, upsert_sql, data_tuples,
                    template=None, page_size=1000
                )

                results = cursor.fetchall()
                total_upserts = len(results)
                
                # Check if results have the expected structure
                if results:
                    if isinstance(results[0], (list, tuple)) and len(results[0]) >= 3:
                        new_records = sum(1 for result in results if result[2])
                    elif hasattr(results[0], 'was_inserted'):
                        new_records = sum(1 for result in results if result.was_inserted)
                    else:
                        # Fallback: assume all are new records
                        new_records = total_upserts
                else:
                    new_records = 0
                    
                updated_records = total_upserts - new_records

                return total_upserts, new_records, updated_records
    
    def load_data(self, csv_file_path: Path) -> bool:
        """Load data from CSV file into the database with batch processing and duplicate handling."""
        if not self.validate_csv_file(csv_file_path):
            return False
        
        try:
            # 1. Get total row count for progress tracking
            print_info(f"Analyzing CSV file size: {csv_file_path}")
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f)
            print_success(f"CSV file analyzed: {total_rows:,} total records")

            # 2. Define batch size for processing (smaller for stability)
            BATCH_SIZE = 10000
            estimated_batches = (total_rows // BATCH_SIZE) + 1
            print_info(f"Starting batch processing: {BATCH_SIZE:,} records per batch ({estimated_batches} estimated batches)")

            # Statistics tracking
            total_processed = 0
            total_duplicates_removed = 0
            total_upserts = 0
            total_new_records = 0
            total_updated_records = 0
            batch_number = 0

            print("")
            print(f"{Colors.GREEN}=========================================={Colors.ENDC}")
            print(f"{Colors.GREEN}  Starting Historical Data Load Process  {Colors.ENDC}")
            print(f"{Colors.GREEN}=========================================={Colors.ENDC}")
            print("")

            # 3. Process file in chunks
            for chunk in pd.read_csv(csv_file_path, names=self.csv_columns, encoding='utf-8', chunksize=BATCH_SIZE):
                batch_number += 1
                original_batch_size = len(chunk)
                
                print_batch(f"Batch {batch_number}: Processing {original_batch_size:,} records...")
                
                # Handle duplicates within this batch (more robust)
                print_info("  → Removing duplicates within batch...")
                
                # First, sort by a stable column to ensure consistent ordering
                chunk_sorted = chunk.sort_values(['salesinvoiceid', 'items_product_sku', 'docnumber'])
                
                # Then remove duplicates keeping the last occurrence
                chunk_deduped = chunk_sorted.drop_duplicates(
                    subset=['salesinvoiceid', 'items_product_sku'], 
                    keep='last'
                ).copy()
                
                deduped_batch_size = len(chunk_deduped)
                batch_duplicates = original_batch_size - deduped_batch_size
                
                # Additional verification: ensure no duplicates remain
                duplicate_check = chunk_deduped.duplicated(subset=['salesinvoiceid', 'items_product_sku'])
                if duplicate_check.any():
                    print_warning(f"  → Still found {duplicate_check.sum()} duplicates after first pass, forcing additional cleanup...")
                    # Force another round of deduplication
                    chunk_deduped = chunk_deduped.drop_duplicates(
                        subset=['salesinvoiceid', 'items_product_sku'], 
                        keep='last'
                    ).copy()
                    print_success("  → Additional deduplication completed")
                
                print_info("  → Converting date formats...")
                chunk_deduped.loc[:, 'issueddate'] = pd.to_datetime(chunk_deduped['issueddate']).dt.date
                
                print_info(f"  → Upserting {len(chunk_deduped):,} unique records to database...")
                # Perform upsert for this batch
                batch_upserts, batch_new, batch_updated = self.bulk_upsert_sales_data(chunk_deduped)
                
                # Update statistics
                total_processed += original_batch_size
                total_duplicates_removed += batch_duplicates
                total_upserts += batch_upserts
                total_new_records += batch_new
                total_updated_records += batch_updated
                
                # Log batch completion
                progress_pct = (total_processed / total_rows) * 100
                print_success(f"  → Batch {batch_number} completed: {batch_upserts:,} upserted ({batch_new:,} new, {batch_updated:,} updated, {batch_duplicates:,} duplicates removed)")
                print_progress(f"  → Progress: {total_processed:,}/{total_rows:,} records ({progress_pct:.1f}%)")
                print("")

            # 4. Final verification
            print_info("Performing final verification...")
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) as total FROM sales_items")
                    final_count = cursor.fetchone()['total']
                    
                    cursor.execute("""
                        SELECT MIN(issueddate) as earliest_date, 
                               MAX(issueddate) as latest_date,
                               COUNT(DISTINCT salesinvoiceid) as unique_invoices
                        FROM sales_items
                    """)
                    stats = cursor.fetchone()

            # 5. Summary report
            print("")
            print(f"{Colors.GREEN}=" * 60 + Colors.ENDC)
            print(f"{Colors.GREEN}📊 BATCH PROCESSING SUMMARY:{Colors.ENDC}")
            print(f"  Total CSV records processed: {total_processed:,}")
            print(f"  Total duplicates removed: {total_duplicates_removed:,}")
            print(f"  Total unique records: {total_processed - total_duplicates_removed:,}")
            print(f"  Records in database: {final_count:,}")
            print(f"  Total upserts performed: {total_upserts:,}")
            print(f"  New records inserted: {total_new_records:,}")
            print(f"  Existing records updated: {total_updated_records:,}")
            print(f"  Date range: {stats['earliest_date']} to {stats['latest_date']}")
            print(f"  Unique invoices: {stats['unique_invoices']:,}")
            print(f"  Batches processed: {batch_number}")
            print(f"{Colors.GREEN}=" * 60 + Colors.ENDC)
                
            return True
        
        except Exception as e:
            import traceback
            print_error(f"Failed to load historical data: {e}")
            traceback.print_exc()
            return False
    



def main():
    """Main entry point for the historical data loader."""
    if len(sys.argv) != 2:
        print("Usage: python load_historical_data.py <csv_file_path>")
        print("Example: python load_historical_data.py historic_sales.csv")
        sys.exit(1)
    
    csv_file_path = Path(sys.argv[1])
    
    print("")
    print(f"{Colors.BLUE}🚀 Historical Data Loader Starting{Colors.ENDC}")
    print(f"   Target file: {csv_file_path}")
    print("")
    
    try:
        loader = HistoricalDataLoader()
        
        # Load the data
        success = loader.load_data(csv_file_path)
        
        if success:
            print("")
            print_success("Historical data loaded successfully!")
            print_info("Data processed in batches of 10,000 records with automatic duplicate handling.")
            print_info("Check the summary above for detailed batch processing statistics.")
            sys.exit(0)
        else:
            print_error("Historical data load failed. Check logs for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("")
        print_warning("Load interrupted by user")
        sys.exit(1)
    except Exception as e:
        import traceback
        print_error(f"Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
