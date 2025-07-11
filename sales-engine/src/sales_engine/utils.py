#Standard library imports
from typing import Dict, Any

# Third-party imports
import psycopg2

# Function to create the sales_items table
def create_sales_items_table(connection_params: Dict[str, Any]):
    """
    Create the sales_items table with proper schema and indexes.
    Args:
        connection_params: Database connection parameters
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS sales_items (
        id SERIAL PRIMARY KEY,
        salesInvoiceId VARCHAR(50) NOT NULL,
        doctype_name VARCHAR(100),
        docnumber VARCHAR(50),
        customer_customerid INTEGER,
        customer_name VARCHAR(255),
        customer_vatid VARCHAR(20),
        salesman_name VARCHAR(255),
        term_name VARCHAR(100),
        warehouse_name VARCHAR(100),
        totals_net NUMERIC(15, 2),
        totals_vat NUMERIC(15, 2),
        total_total NUMERIC(15, 2),
        items_product_description VARCHAR(255),
        items_product_sku VARCHAR(50) NOT NULL,
        items_quantity NUMERIC(10, 2),
        items_unitPrice NUMERIC(15, 2),
        issuedDate DATE,
        sales_channel VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create indexes for performance
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_items_invoice_sku 
    ON sales_items (salesInvoiceId, items_product_sku);

    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_items_issued_date 
    ON sales_items (issuedDate DESC);

    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_items_customer 
    ON sales_items (customer_customerid);

    -- Create unique constraint to prevent duplicates
    ALTER TABLE sales_items ADD CONSTRAINT unique_invoice_sku_date 
    UNIQUE (salesInvoiceId, items_product_sku, issuedDate);
    """

    try:
        conn = psycopg2.connect(**connection_params)
        with conn.cursor() as cursor:
            cursor.execute(create_table_sql)
        conn.commit()
        conn.close()
        print("sales_items table created successfully")
    except Exception as e:
        print(f"Error creating table: {e}")