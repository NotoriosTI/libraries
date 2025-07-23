"""
One-time script to load historical sales data from a headerless CSV file
into the sales_items table after schema refactoring.

This script handles:
- Headerless CSV files
- Efficient bulk loading using psycopg2's copy_expert
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
from psycopg2.extras import RealDictCursor
import structlog
from typing import Optional
from pathlib import Path

# Import the centralized configuration
from config_manager import secrets

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class HistoricalDataLoader:
    """Loads historical sales data from headerless CSV files."""
    
    def __init__(self):
        """Initialize the loader with database configuration."""
        self.logger = logger.bind(component="historical_data_loader")
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
        
        self.logger.info("HistoricalDataLoader initialized", 
                        database=self.db_config.get('database', 'salesdb'),
                        csv_columns_count=len(self.csv_columns))
    
    def get_connection(self):
        """Create a database connection."""
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=int(self.db_config['port']),
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                cursor_factory=RealDictCursor
            )
            self.logger.info("Database connection established")
            return conn
        except Exception as e:
            self.logger.error("Failed to connect to database", error=str(e))
            raise
    
    def validate_csv_file(self, csv_file_path: Path) -> bool:
        """Validate that the CSV file exists and is readable."""
        if not csv_file_path.exists():
            self.logger.error("CSV file does not exist", path=str(csv_file_path))
            return False
        
        if not csv_file_path.is_file():
            self.logger.error("Path is not a file", path=str(csv_file_path))
            return False
        
        try:
            # Check if file is readable and estimate row count
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    self.logger.error("CSV file appears to be empty")
                    return False
                
                # Count columns in first line
                column_count = len(first_line.split(','))
                if column_count != len(self.csv_columns):
                    self.logger.warning(
                        "Column count mismatch",
                        expected=len(self.csv_columns),
                        found=column_count,
                        first_line_preview=first_line[:100] + "..." if len(first_line) > 100 else first_line
                    )
                
                # Estimate total rows (for progress reporting)
                f.seek(0)
                estimated_rows = sum(1 for _ in f)
                
            self.logger.info("CSV file validated", 
                           path=str(csv_file_path),
                           estimated_rows=estimated_rows,
                           columns_found=column_count)
            return True
            
        except Exception as e:
            self.logger.error("Failed to validate CSV file", path=str(csv_file_path), error=str(e))
            return False
    
    def load_data(self, csv_file_path: Path) -> bool:
        """Load data from CSV file into the database."""
        if not self.validate_csv_file(csv_file_path):
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    self.logger.info("Starting bulk data load", csv_file=str(csv_file_path))
                    
                    # Use COPY command for optimal performance
                    # Note: We exclude created_at and updated_at from the column list
                    # so the database can auto-fill them with CURRENT_TIMESTAMP
                    columns_str = ', '.join(self.csv_columns)
                    
                    copy_sql = f"""
                    COPY sales_items ({columns_str})
                    FROM STDIN
                    WITH (
                        FORMAT CSV,
                        DELIMITER ',',
                        NULL '',
                        ENCODING 'UTF8'
                    )
                    """
                    
                    # Open file and execute COPY
                    with open(csv_file_path, 'r', encoding='utf-8') as f:
                        try:
                            cursor.copy_expert(copy_sql, f)
                            rows_loaded = cursor.rowcount
                            
                            # Commit the transaction
                            conn.commit()
                            
                            self.logger.info("Data loaded successfully", 
                                           rows_loaded=rows_loaded,
                                           csv_file=str(csv_file_path))
                            
                            # Verify the load
                            cursor.execute("SELECT COUNT(*) as total FROM sales_items")
                            total_rows = cursor.fetchone()['total']
                            
                            cursor.execute("""
                                SELECT MIN(issueddate) as earliest_date, 
                                       MAX(issueddate) as latest_date,
                                       COUNT(DISTINCT salesinvoiceid) as unique_invoices
                                FROM sales_items
                            """)
                            stats = cursor.fetchone()
                            
                            self.logger.info("Load verification completed",
                                           total_rows_in_table=total_rows,
                                           earliest_date=str(stats['earliest_date']),
                                           latest_date=str(stats['latest_date']),
                                           unique_invoices=stats['unique_invoices'])
                            
                            return True
                            
                        except psycopg2.Error as e:
                            conn.rollback()
                            self.logger.error("Database error during COPY operation", 
                                            error=str(e),
                                            pgcode=getattr(e, 'pgcode', None))
                            return False
        
        except Exception as e:
            self.logger.error("Failed to load historical data", error=str(e))
            return False
    
    def check_for_duplicates(self) -> None:
        """Check for potential duplicate records after loading."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check for duplicate primary key combinations
                    cursor.execute("""
                        SELECT salesinvoiceid, items_product_sku, COUNT(*) as duplicate_count
                        FROM sales_items
                        GROUP BY salesinvoiceid, items_product_sku
                        HAVING COUNT(*) > 1
                        ORDER BY duplicate_count DESC
                        LIMIT 10
                    """)
                    
                    duplicates = cursor.fetchall()
                    if duplicates:
                        self.logger.warning("Found duplicate records", duplicate_count=len(duplicates))
                        for dup in duplicates:
                            self.logger.warning("Duplicate record", 
                                              invoice_id=dup['salesinvoiceid'],
                                              product_sku=dup['items_product_sku'],
                                              count=dup['duplicate_count'])
                    else:
                        self.logger.info("No duplicate records found")
                        
        except Exception as e:
            self.logger.error("Failed to check for duplicates", error=str(e))


def main():
    """Main entry point for the historical data loader."""
    if len(sys.argv) != 2:
        print("Usage: python load_historical_data.py <csv_file_path>")
        print("Example: python load_historical_data.py historic_sales.csv")
        sys.exit(1)
    
    csv_file_path = Path(sys.argv[1])
    
    logger.info("Historical data load starting", csv_file=str(csv_file_path))
    
    try:
        loader = HistoricalDataLoader()
        
        # Load the data
        success = loader.load_data(csv_file_path)
        
        if success:
            # Check for duplicates
            loader.check_for_duplicates()
            
            logger.info("Historical data load completed successfully")
            print("✅ Historical data loaded successfully!")
            sys.exit(0)
        else:
            logger.error("Historical data load failed")
            print("❌ Historical data load failed. Check logs for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Historical data load interrupted by user")
        print("⚠️ Load interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error during historical data load", error=str(e), exc_info=True)
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()