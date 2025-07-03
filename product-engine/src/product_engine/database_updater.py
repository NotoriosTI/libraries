"""
Database updater module for products synchronization.

This module provides the ProductDBUpdater class for managing product data
in PostgreSQL with pgvector support for embeddings.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from contextlib import contextmanager
import io
import pandas as pd
import psycopg2
import psycopg2.pool
from psycopg2.extras import execute_values, RealDictCursor
import structlog

from .config import config

logger = structlog.get_logger(__name__)


class ProductDBUpdater:
    """
    Database updater for product catalog synchronization.
    
    Handles all database operations including table creation, upserts,
    deactivation, and embedding updates with pgvector support.
    """
    
    def __init__(self):
        """Initialize the database updater with configuration."""
        self.logger = logger.bind(component="product_db_updater")
        self.config = config
        self._connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        
        self.logger.info(
            "ProductDBUpdater initialized",
            environment=self.config.environment
        )
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Get database connection parameters from configuration."""
        try:
            db_config = self.config.get_database_config()
            
            # Ensure port is an integer
            db_config['port'] = int(db_config['port'])
            
            # Filter to only include valid PostgreSQL connection parameters
            valid_params = {
                'host', 'port', 'database', 'user', 'password', 'dbname',
                'connect_timeout', 'sslmode', 'application_name'
            }
            
            filtered_config = {k: v for k, v in db_config.items() if k in valid_params}
            
            # Set application name for easier monitoring
            filtered_config['application_name'] = 'product-engine'
            
            return filtered_config
            
        except Exception as e:
            self.logger.error("Failed to get database configuration", error=str(e))
            raise RuntimeError("Database configuration error") from e
    
    def _setup_connection_pool(self):
        """Initialize the database connection pool."""
        if self._connection_pool:
            return
            
        try:
            params = self._get_connection_params()
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                **params,
                connect_timeout=30
            )
            
            self.logger.info(
                "Database connection pool created",
                host=params.get('host'),
                database=params.get('database')
            )
            
        except Exception as e:
            self.logger.error("Failed to create connection pool", error=str(e))
            raise RuntimeError("Failed to create database connection pool") from e
    
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
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error("Database transaction failed", error=str(e))
            raise
        finally:
            if conn:
                self._connection_pool.putconn(conn)
    
    def create_products_table(self):
        """
        Create the products table with pgvector support if it doesn't exist.
        """
        self.logger.info("Creating products table...")
        
        create_extension_sql = """
        CREATE EXTENSION IF NOT EXISTS vector;
        """
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS products (
            sku VARCHAR(100) PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            description TEXT,
            category_id INTEGER,
            category_name VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            list_price NUMERIC(15, 2) DEFAULT 0,
            standard_price NUMERIC(15, 2) DEFAULT 0,
            product_type VARCHAR(50),
            barcode VARCHAR(100),
            weight NUMERIC(10, 3) DEFAULT 0,
            volume NUMERIC(10, 3) DEFAULT 0,
            sale_ok BOOLEAN DEFAULT TRUE,
            purchase_ok BOOLEAN DEFAULT TRUE,
            uom_id INTEGER,
            uom_name VARCHAR(100),
            company_id INTEGER,
            text_for_embedding TEXT,
            embedding VECTOR(1536),
            last_update TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_indexes_sql = """
        -- Index for SKU lookups (already primary key)
        -- Index for active products
        CREATE INDEX IF NOT EXISTS idx_products_active ON products (is_active);
        
        -- Index for category lookups
        CREATE INDEX IF NOT EXISTS idx_products_category ON products (category_id);
        
        -- Index for last update (for incremental sync)
        CREATE INDEX IF NOT EXISTS idx_products_last_update ON products (last_update);
        
        -- Index for product type
        CREATE INDEX IF NOT EXISTS idx_products_type ON products (product_type);
        
        -- Vector similarity index (using HNSW algorithm)
        CREATE INDEX IF NOT EXISTS idx_products_embedding ON products 
        USING hnsw (embedding vector_cosine_ops);
        """
        
        create_trigger_sql = """
        -- Create trigger function for updated_at
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        -- Create trigger
        DROP TRIGGER IF EXISTS update_products_updated_at ON products;
        CREATE TRIGGER update_products_updated_at
            BEFORE UPDATE ON products
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Create extension
                    cursor.execute(create_extension_sql)
                    self.logger.info("pgvector extension created/verified")
                    
                    # Create table
                    cursor.execute(create_table_sql)
                    self.logger.info("Products table created/verified")
                    
                    # Create indexes
                    cursor.execute(create_indexes_sql)
                    self.logger.info("Database indexes created/verified")
                    
                    # Create trigger
                    cursor.execute(create_trigger_sql)
                    self.logger.info("Database triggers created/verified")
            
            self.logger.info("Database schema setup completed successfully")
            
        except Exception as e:
            self.logger.error("Failed to create products table", error=str(e))
            raise RuntimeError("Failed to create database schema") from e
    
    def upsert_products(self, products_df: pd.DataFrame) -> List[str]:
        """
        Upsert products using temporary table for efficient bulk operations.
        
        Args:
            products_df: DataFrame containing product data
            
        Returns:
            List of SKUs that were affected (inserted or updated)
        """
        if products_df.empty:
            self.logger.info("No products to upsert")
            return []
        
        self.logger.info(f"Starting upsert for {len(products_df)} products")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Create temporary table
                    cursor.execute("""
                        CREATE TEMP TABLE temp_products (
                            sku VARCHAR(100),
                            name VARCHAR(500),
                            description TEXT,
                            category_id INTEGER,
                            category_name VARCHAR(255),
                            is_active BOOLEAN,
                            list_price NUMERIC(15, 2),
                            standard_price NUMERIC(15, 2),
                            product_type VARCHAR(50),
                            barcode VARCHAR(100),
                            weight NUMERIC(10, 3),
                            volume NUMERIC(10, 3),
                            sale_ok BOOLEAN,
                            purchase_ok BOOLEAN,
                            uom_id INTEGER,
                            uom_name VARCHAR(100),
                            company_id INTEGER,
                            text_for_embedding TEXT,
                            last_update TIMESTAMP WITH TIME ZONE
                        );
                    """)
                    
                    # Prepare data for insertion
                    columns = [
                        'sku', 'name', 'description', 'category_id', 'category_name',
                        'is_active', 'list_price', 'standard_price', 'product_type',
                        'barcode', 'weight', 'volume', 'sale_ok', 'purchase_ok',
                        'uom_id', 'uom_name', 'company_id', 'text_for_embedding',
                        'last_update'
                    ]
                    
                    # Prepare data tuples
                    data_tuples = []
                    for _, row in products_df.iterrows():
                        tuple_data = []
                        for col in columns:
                            value = row.get(col)
                            # Handle NaN and None values
                            if pd.isna(value) or value is None:
                                tuple_data.append(None)
                            else:
                                tuple_data.append(value)
                        data_tuples.append(tuple(tuple_data))
                    
                    # Bulk insert into temporary table
                    execute_values(
                        cursor,
                        f"INSERT INTO temp_products ({', '.join(columns)}) VALUES %s",
                        data_tuples,
                        page_size=1000
                    )
                    
                    self.logger.info(f"Inserted {len(data_tuples)} records into temporary table")
                    
                    # Perform upsert from temporary table
                    upsert_sql = """
                        INSERT INTO products (
                            sku, name, description, category_id, category_name,
                            is_active, list_price, standard_price, product_type,
                            barcode, weight, volume, sale_ok, purchase_ok,
                            uom_id, uom_name, company_id, text_for_embedding,
                            last_update
                        )
                        SELECT 
                            sku, name, description, category_id, category_name,
                            is_active, list_price, standard_price, product_type,
                            barcode, weight, volume, sale_ok, purchase_ok,
                            uom_id, uom_name, company_id, text_for_embedding,
                            last_update
                        FROM temp_products
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            category_id = EXCLUDED.category_id,
                            category_name = EXCLUDED.category_name,
                            is_active = EXCLUDED.is_active,
                            list_price = EXCLUDED.list_price,
                            standard_price = EXCLUDED.standard_price,
                            product_type = EXCLUDED.product_type,
                            barcode = EXCLUDED.barcode,
                            weight = EXCLUDED.weight,
                            volume = EXCLUDED.volume,
                            sale_ok = EXCLUDED.sale_ok,
                            purchase_ok = EXCLUDED.purchase_ok,
                            uom_id = EXCLUDED.uom_id,
                            uom_name = EXCLUDED.uom_name,
                            company_id = EXCLUDED.company_id,
                            text_for_embedding = EXCLUDED.text_for_embedding,
                            last_update = EXCLUDED.last_update
                        RETURNING sku;
                    """
                    
                    cursor.execute(upsert_sql)
                    affected_skus = [row[0] for row in cursor.fetchall()]
                    
                    self.logger.info(f"Upsert completed, {len(affected_skus)} products affected")
                    return affected_skus
            
        except Exception as e:
            self.logger.error("Failed to upsert products", error=str(e))
            raise RuntimeError("Product upsert failed") from e
    
    def deactivate_missing_products(self, active_skus: Set[str]) -> int:
        """
        Deactivate products that are no longer active in Odoo.
        
        Args:
            active_skus: Set of currently active SKUs from Odoo
            
        Returns:
            Number of products deactivated
        """
        self.logger.info(f"Deactivating products not in {len(active_skus)} active SKUs")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if active_skus:
                        # Convert set to list for SQL IN clause
                        active_skus_list = list(active_skus)
                        
                        deactivate_sql = """
                            UPDATE products 
                            SET is_active = false 
                            WHERE is_active = true AND sku NOT IN %s
                        """
                        
                        cursor.execute(deactivate_sql, (tuple(active_skus_list),))
                        deactivated_count = cursor.rowcount
                    else:
                        # If no active SKUs, deactivate all products
                        cursor.execute("""
                            UPDATE products 
                            SET is_active = false 
                            WHERE is_active = true
                        """)
                        deactivated_count = cursor.rowcount
                    
                    self.logger.info(f"Deactivated {deactivated_count} products")
                    return deactivated_count
            
        except Exception as e:
            self.logger.error("Failed to deactivate products", error=str(e))
            raise RuntimeError("Product deactivation failed") from e
    
    def update_embeddings(self, sku_embeddings: List[Tuple[str, List[float]]]) -> int:
        """
        Update embeddings for specified products.
        
        Args:
            sku_embeddings: List of tuples (sku, embedding_vector)
            
        Returns:
            Number of embeddings updated
        """
        if not sku_embeddings:
            self.logger.info("No embeddings to update")
            return 0
        
        self.logger.info(f"Updating embeddings for {len(sku_embeddings)} products")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Prepare data for batch update
                    update_data = [
                        (embedding, sku) for sku, embedding in sku_embeddings
                    ]
                    
                    update_sql = """
                        UPDATE products 
                        SET embedding = %s::vector
                        WHERE sku = %s
                    """
                    
                    # Use execute_values for efficient batch update
                    cursor.executemany(update_sql, update_data)
                    updated_count = cursor.rowcount
                    
                    self.logger.info(f"Updated {updated_count} embeddings")
                    return updated_count
            
        except Exception as e:
            self.logger.error("Failed to update embeddings", error=str(e))
            raise RuntimeError("Embedding update failed") from e
    
    def get_last_sync_date(self) -> Optional[str]:
        """
        Get the last synchronization date from the database.
        
        Returns:
            Last sync date as ISO string, or None if no products exist
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT MAX(last_update) 
                        FROM products 
                        WHERE last_update IS NOT NULL
                    """)
                    
                    result = cursor.fetchone()
                    last_date = result[0] if result and result[0] else None
                    
                    if last_date:
                        # Convert to ISO string format for Odoo domain filtering
                        last_date_str = last_date.isoformat()
                        self.logger.info(f"Last sync date: {last_date_str}")
                        return last_date_str
                    else:
                        self.logger.info("No previous sync date found")
                        return None
            
        except Exception as e:
            self.logger.error("Failed to get last sync date", error=str(e))
            return None
    
    def get_products_needing_embeddings(self, limit: Optional[int] = None) -> List[Tuple[str, str]]:
        """
        Get products that need embeddings generated.
        
        Args:
            limit: Maximum number of products to return
            
        Returns:
            List of tuples (sku, text_for_embedding)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT sku, text_for_embedding 
                        FROM products 
                        WHERE embedding IS NULL 
                        AND text_for_embedding IS NOT NULL
                        AND is_active = true
                        ORDER BY updated_at DESC
                    """
                    
                    if limit:
                        sql += f" LIMIT {limit}"
                    
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    
                    self.logger.info(f"Found {len(results)} products needing embeddings")
                    return results
            
        except Exception as e:
            self.logger.error("Failed to get products needing embeddings", error=str(e))
            return []
    
    def close(self):
        """Clean up database connections."""
        try:
            if self._connection_pool:
                self._connection_pool.closeall()
                self.logger.info("Database connection pool closed")
        except Exception as e:
            self.logger.error("Error closing database connections", error=str(e))


def create_table_main():
    """Main function for creating the products table via CLI."""
    import structlog
    
    # Configure basic logging for CLI usage
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger()
    
    try:
        logger.info("Creating products table...")
        updater = ProductDBUpdater()
        updater.create_products_table()
        logger.info("Products table created successfully")
    except Exception as e:
        logger.error("Failed to create products table", error=str(e))
        raise


if __name__ == "__main__":
    create_table_main() 