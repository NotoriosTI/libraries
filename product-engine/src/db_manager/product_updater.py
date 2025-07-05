"""
Product updater for database write operations.

This module provides all database write operations including table creation,
upserts, deactivation, and embedding updates for the product catalog.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import io
import pandas as pd
from psycopg2.extras import execute_values
import structlog

from common.database import database
from common.models import ProductData

logger = structlog.get_logger(__name__)


class ProductUpdater:
    """
    Database updater for product catalog write operations.
    
    Handles all database write operations including table creation, upserts,
    deactivation, and embedding updates with pgvector support.
    """
    
    def __init__(self):
        """Initialize the product updater."""
        self.logger = logger.bind(component="product_updater")
        self.logger.info("ProductUpdater initialized")
    
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
            with database.get_cursor() as cursor:
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
        Upsert products into the database using bulk operations.
        
        Args:
            products_df: DataFrame with product data
            
        Returns:
            List of affected SKUs
        """
        with database.get_connection() as conn:
            with conn.cursor() as cursor:
                # Create temporary table for bulk operations
                temp_table_sql = """
                    CREATE TEMP TABLE temp_products (
                        sku VARCHAR(100) PRIMARY KEY,
                        name VARCHAR(255),
                        description TEXT,
                        category_id INTEGER,
                        category_name VARCHAR(255),
                        is_active BOOLEAN,
                        list_price DECIMAL(10,2),
                        standard_price DECIMAL(10,2),
                        product_type VARCHAR(100),
                        barcode VARCHAR(100),
                        weight DECIMAL(10,2),
                        volume DECIMAL(10,2),
                        sale_ok BOOLEAN,
                        purchase_ok BOOLEAN,
                        uom_id INTEGER,
                        uom_name VARCHAR(100),
                        company_id INTEGER,
                        text_for_embedding TEXT,
                        last_update TIMESTAMP
                    ) ON COMMIT DROP;
                """
                
                cursor.execute(temp_table_sql)
                
                # Prepare data for bulk insert
                columns = [
                    'sku', 'name', 'description', 'category_id', 'category_name',
                    'is_active', 'list_price', 'standard_price', 'product_type',
                    'barcode', 'weight', 'volume', 'sale_ok', 'purchase_ok',
                    'uom_id', 'uom_name', 'company_id', 'text_for_embedding', 'last_update'
                ]
                
                # Field length limits for validation
                varchar_100_fields = {'sku', 'product_type', 'barcode', 'uom_name'}
                varchar_255_fields = {'name', 'category_name'}
                varchar_500_fields = {'description'}
                many2one_fields = {'category_id', 'uom_id', 'company_id'}
                
                data_tuples = []
                seen_skus = set()
                duplicate_skus = set()
                filtered_products = []
                
                self.logger.info(f"Processing {len(products_df)} products for upsert...")
                
                for idx, row in products_df.iterrows():
                    # Validate field lengths and log warnings
                    for field in ['name', 'description', 'category_name']:
                        if field in row and row[field]:
                            value = str(row[field])
                            if len(value) > 100:
                                self.logger.warning(
                                    f"Value too long for {field} (max 100 chars): {value[:50]}... (length: {len(value)})"
                                )
                    
                    # Check for duplicate SKUs
                    sku = row.get('sku', '')
                    if sku in seen_skus:
                        duplicate_skus.add(sku)
                        filtered_products.append({
                            'reason': 'duplicate_sku',
                            'sku': sku,
                            'name': str(row.get('name', 'NULL')),
                            'row_index': idx
                        })
                        continue  # Skip duplicate SKUs
                    seen_skus.add(sku)
                    
                    # Validate SKU format
                    if not sku or sku == 'None' or sku == 'False':
                        filtered_products.append({
                            'reason': 'invalid_sku_format',
                            'sku': str(sku),
                            'name': str(row.get('name', 'NULL')),
                            'row_index': idx
                        })
                        continue
                    
                    # Process row data
                    tuple_data = self._process_row_data(row, columns, many2one_fields, varchar_100_fields, varchar_255_fields, varchar_500_fields)
                    if tuple_data is None:
                        filtered_products.append({
                            'reason': 'processing_error',
                            'sku': sku,
                            'name': str(row.get('name', 'NULL')),
                            'row_index': idx
                        })
                        continue
                    
                    data_tuples.append(tuple_data)
                
                # Log detailed information about filtered products
                self._log_filtered_products(filtered_products)
                
                # Bulk insert into temporary table
                execute_values(
                    cursor,
                    f"INSERT INTO temp_products ({', '.join(columns)}) VALUES %s",
                    data_tuples,
                    page_size=1000
                )
                
                # Log duplicate SKUs found
                if duplicate_skus:
                    self.logger.warning(f"Found {len(duplicate_skus)} duplicate SKUs: {list(duplicate_skus)[:10]}{'...' if len(duplicate_skus) > 10 else ''}")
                
                self.logger.info(f"Inserted {len(data_tuples)} records into temporary table (after filtering)")
                
                # Perform upsert from temporary table
                affected_skus = self._perform_upsert(cursor)
                
                # Commit explícito para asegurar persistencia de los datos
                conn.commit()
                
                self.logger.info(f"Upsert completed, {len(affected_skus)} products affected")
                return affected_skus
    
    def _process_row_data(self, row, columns, many2one_fields, varchar_100_fields, varchar_255_fields, varchar_500_fields):
        """Process a single row and return tuple data for database insertion."""
        try:
            tuple_data = []
            for col in columns:
                value = row[col]
                processed_value = self._process_field_value(value, col, many2one_fields, varchar_100_fields, varchar_255_fields, varchar_500_fields)
                tuple_data.append(processed_value)
            return tuple(tuple_data)
        except Exception as e:
            self.logger.error(f"Error processing row data: {str(e)}")
            return None
    
    def _process_field_value(self, value, col, many2one_fields, varchar_100_fields, varchar_255_fields, varchar_500_fields):
        """Process a single field value with proper type handling."""
        # Handle Many2one fields (extract ID from tuple/list)
        if col in many2one_fields:
            return self._process_many2one_value(value)
        
        # Handle pandas Series/DataFrame values
        if hasattr(value, 'isna'):
            return self._process_pandas_value(value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields)
        
        # Handle list/tuple values
        if isinstance(value, (list, tuple)):
            return self._process_list_value(value)
        
        # Handle regular values
        return self._process_regular_value(value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields)
    
    def _process_many2one_value(self, value):
        """Process Many2one field value (extract ID from tuple/list)."""
        if isinstance(value, (list, tuple)) and len(value) > 0:
            id_val = value[0]
            return int(id_val) if isinstance(id_val, (int, float)) else None
        elif isinstance(value, (int, float)):
            return int(value)
        return None
    
    def _process_pandas_value(self, value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields):
        """Process pandas Series/DataFrame value."""
        if hasattr(value, 'any'):
            # DataFrame column
            if value.isna().any():
                return None
            
            try:
                processed_value = value.item()
            except ValueError:
                if len(value) > 0:
                    first_val = value.iloc[0]
                    if hasattr(first_val, 'item'):
                        try:
                            processed_value = first_val.item()
                        except ValueError:
                            processed_value = str(first_val)
                    else:
                        processed_value = first_val
                else:
                    processed_value = None
        else:
            # Series value
            if value.isna():
                return None
            
            try:
                processed_value = value.item()
            except ValueError:
                processed_value = str(value)
        
        return self._truncate_string_value(processed_value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields)
    
    def _process_list_value(self, value):
        """Process list/tuple value."""
        if not value or all(hasattr(item, 'isna') and item.isna() for item in value):
            return None
        return value
    
    def _process_regular_value(self, value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields):
        """Process regular value."""
        return self._truncate_string_value(value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields)
    
    def _truncate_string_value(self, value, col, varchar_100_fields, varchar_255_fields, varchar_500_fields):
        """Truncate string values according to database limits."""
        if not isinstance(value, str):
            return value
        
        if col in varchar_100_fields and len(value) > 100:
            return value[:100]
        elif col in varchar_255_fields and len(value) > 255:
            return value[:255]
        elif col in varchar_500_fields and len(value) > 500:
            return value[:500]
        
        return value
    
    def _log_filtered_products(self, filtered_products):
        """Log detailed information about filtered products."""
        if not filtered_products:
            return
        
        self.logger.warning(f"Filtered out {len(filtered_products)} products during upsert processing:")
        
        # Group by reason
        reasons = {}
        for product in filtered_products:
            reason = product['reason']
            if reason not in reasons:
                reasons[reason] = []
            reasons[reason].append(product)
        
        # Log each reason with examples
        for reason, products in reasons.items():
            reason_descriptions = {
                'duplicate_sku': 'products with duplicate SKUs',
                'invalid_sku_format': 'products with invalid SKU format',
                'processing_error': 'products with processing errors'
            }
            
            self.logger.warning(f"  - {len(products)} {reason_descriptions.get(reason, reason)}")
            
            # Log first 3 examples for each reason
            for product in products[:3]:
                self.logger.warning(f"    Example: SKU='{product['sku']}', Name='{product['name']}'")
            
            if len(products) > 3:
                self.logger.warning(f"    ... and {len(products) - 3} more")
    
    def _perform_upsert(self, cursor):
        """Perform upsert operation from temporary table."""
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
        return [row['sku'] for row in cursor.fetchall()]
    
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
            if active_skus:
                # Convert set to list for SQL IN clause
                active_skus_list = list(active_skus)
                
                deactivate_sql = """
                    UPDATE products 
                    SET is_active = false 
                    WHERE is_active = true AND sku NOT IN %s
                """
                
                deactivated_count = database.execute_update(
                    deactivate_sql, 
                    (tuple(active_skus_list),)
                )
            else:
                # If no active SKUs, deactivate all products
                deactivated_count = database.execute_update("""
                    UPDATE products 
                    SET is_active = false 
                    WHERE is_active = true
                """)
            
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
            # Prepare data for batch update
            update_data = [
                (embedding, sku) for sku, embedding in sku_embeddings
            ]
            
            update_sql = """
                UPDATE products 
                SET embedding = %s::vector
                WHERE sku = %s
            """
            
            # Use execute_batch for efficient batch update
            updated_count = database.execute_batch(update_sql, update_data)
            
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
            result = database.execute_query(
                """
                SELECT MAX(last_update) as last_date
                FROM products 
                WHERE last_update IS NOT NULL
                """,
                fetch_one=True
            )
            
            last_date = result['last_date'] if result and result.get('last_date') else None
            
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
            sql = """
                SELECT sku, text_for_embedding 
                FROM products 
                WHERE embedding IS NULL 
                AND text_for_embedding IS NOT NULL
                AND is_active = true
                ORDER BY updated_at DESC
            """
            
            params = None
            if limit:
                sql += " LIMIT %s"
                params = (limit,)
            
            results = database.execute_query(sql, params)
            
            # Convert to list of tuples
            product_tuples = [(row['sku'], row['text_for_embedding']) for row in results] if results else []
            
            self.logger.info(f"Found {len(product_tuples)} products needing embeddings")
            return product_tuples
        
        except Exception as e:
            self.logger.error("Failed to get products needing embeddings", error=str(e))
            return []
    
    def upsert_product(self, product: ProductData) -> bool:
        """
        Upsert a single product.
        
        Args:
            product: ProductData object to upsert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            upsert_sql = """
                INSERT INTO products (
                    sku, name, description, category_id, category_name,
                    is_active, list_price, standard_price, product_type,
                    barcode, weight, volume, sale_ok, purchase_ok,
                    uom_id, uom_name, company_id, text_for_embedding,
                    last_update, embedding
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
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
                    last_update = EXCLUDED.last_update,
                    embedding = EXCLUDED.embedding
            """
            
            params = (
                product.sku, product.name, product.description,
                product.category_id, product.category_name, product.is_active,
                product.list_price, product.standard_price, product.product_type,
                product.barcode, product.weight, product.volume,
                product.sale_ok, product.purchase_ok, product.uom_id,
                product.uom_name, product.company_id, product.text_for_embedding,
                product.last_update, product.embedding
            )
            
            rows_affected = database.execute_update(upsert_sql, params)
            
            self.logger.info(f"Upserted product {product.sku}", rows_affected=rows_affected)
            return rows_affected > 0
        
        except Exception as e:
            self.logger.error("Failed to upsert single product", error=str(e), sku=product.sku)
            return False
    
    def delete_product(self, sku: str) -> bool:
        """
        Delete a product by SKU.
        
        Args:
            sku: Product SKU to delete
            
        Returns:
            True if product was deleted, False otherwise
        """
        try:
            rows_affected = database.execute_update(
                "DELETE FROM products WHERE sku = %s",
                (sku.upper(),)
            )
            
            self.logger.info(f"Deleted product {sku}", rows_affected=rows_affected)
            return rows_affected > 0
        
        except Exception as e:
            self.logger.error("Failed to delete product", error=str(e), sku=sku)
            return False
    
    def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return database.test_connection()
    
    def close(self):
        """Clean up database connections."""
        try:
            database.close()
            self.logger.info("Database connections closed")
        except Exception as e:
            self.logger.error("Error closing database connections", error=str(e)) 