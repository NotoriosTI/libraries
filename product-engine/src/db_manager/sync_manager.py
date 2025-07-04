"""
Sync Manager for products synchronization orchestration.

This module provides the main orchestrator for the complete process of
syncing products from Odoo to PostgreSQL with OpenAI embeddings generation.
"""
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import structlog

from common.config import config
from common.embedding_generator import EmbeddingGenerator
from db_manager.product_updater import ProductUpdater

# External library imports
from odoo_api.product import OdooProduct as BaseOdooProduct

logger = structlog.get_logger(__name__)


class OdooProduct(BaseOdooProduct):
    """
    Wrapper class for OdooProduct that integrates with product-engine configuration.
    """
    
    def __init__(self, use_test: bool = False):
        """
        Initialize OdooProduct with configuration from config manager.
        
        Args:
            use_test: If True, uses test Odoo configuration
        """
        # Get Odoo configuration
        odoo_config = config.get_odoo_config(use_test=use_test)
        
        # Initialize parent class with configuration
        super().__init__(
            url=odoo_config['url'],
            db=odoo_config['db'],
            username=odoo_config['username'],
            password=odoo_config['password']
        )
        
        self.use_test = use_test


class SyncManager:
    """
    Main orchestrator for products synchronization.
    
    Coordinates the entire process of syncing products from Odoo to PostgreSQL
    with OpenAI embeddings generation.
    """
    
    def __init__(self, use_test_odoo: bool = False):
        """
        Initialize the sync manager.
        
        Args:
            use_test_odoo: Whether to use test Odoo instance
        """
        self.use_test_odoo = use_test_odoo
        self.logger = logger.bind(
            component="sync_manager",
            odoo_env="test" if use_test_odoo else "production"
        )
        
        # Initialize modules
        self.odoo_product: Optional[OdooProduct] = None
        self.product_updater: Optional[ProductUpdater] = None
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        
        self.logger.info("SyncManager initialized")
    
    def _initialize_modules(self):
        """Initialize all required modules."""
        self.logger.info("Initializing modules...")
        
        try:
            # Initialize Odoo API
            self.logger.info("Initializing Odoo API...")
            self.odoo_product = OdooProduct(use_test=self.use_test_odoo)
            
            # Initialize Product Updater
            self.logger.info("Initializing Product Updater...")
            self.product_updater = ProductUpdater()
            
            # Initialize Embedding Generator
            self.logger.info("Initializing Embedding Generator...")
            self.embedding_generator = EmbeddingGenerator()
            
            self.logger.info("All modules initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize modules", error=str(e))
            raise RuntimeError("Module initialization failed") from e
    
    def run_sync(self, force_full_sync: bool = False) -> Dict[str, Any]:
        """
        Run the complete synchronization process.
        
        Args:
            force_full_sync: If True, syncs all products regardless of last sync date
            
        Returns:
            Dictionary with sync results and statistics
        """
        sync_start_time = datetime.now(timezone.utc)
        self.logger.info(
            "Starting products synchronization",
            force_full_sync=force_full_sync,
            start_time=sync_start_time.isoformat()
        )
        
        try:
            # Step 1: Initialize modules
            self._initialize_modules()
            
            # Step 2: Ensure database schema exists
            self.logger.info("Ensuring database schema...")
            self.product_updater.create_products_table()
            
            # Step 3: Get last sync date
            last_sync_date = None if force_full_sync else self.product_updater.get_last_sync_date()
            self.logger.info(f"Last sync date: {last_sync_date}")
            
            # Step 4: Build Odoo domain for incremental sync
            domain = []
            if last_sync_date and not force_full_sync:
                domain = [['write_date', '>', last_sync_date]]
                self.logger.info("Using incremental sync with domain", domain=domain)
            else:
                self.logger.info("Using full sync (no domain filter)")
            
            # Step 5: Extract products from Odoo
            self.logger.info("Extracting products from Odoo...")
            products_df = self.odoo_product.read_products_for_embeddings(domain=domain)
            
            if products_df.empty:
                self.logger.info("No products to sync")
                return {
                    "success": True,
                    "products_processed": 0,
                    "products_upserted": 0,
                    "products_deactivated": 0,
                    "embeddings_generated": 0,
                    "duration_seconds": (datetime.now(timezone.utc) - sync_start_time).total_seconds(),
                    "last_sync_date": last_sync_date
                }
            
            self.logger.info(f"Extracted {len(products_df)} products from Odoo")
            
            # Step 6: Map DataFrame columns to database schema
            products_df = self._map_product_columns(products_df)
            
            # Step 7: Upsert products to database
            self.logger.info("Upserting products to database...")
            affected_skus = self.product_updater.upsert_products(products_df)
            
            # Step 8: Get active SKUs from Odoo and deactivate missing products
            self.logger.info("Getting active SKUs from Odoo...")
            active_skus = self.odoo_product.get_active_skus()
            
            self.logger.info("Deactivating products no longer active in Odoo...")
            deactivated_count = self.product_updater.deactivate_missing_products(active_skus)
            
            # Step 9: Generate embeddings for affected products
            embeddings_generated = 0
            if affected_skus:
                self.logger.info(f"Generating embeddings for {len(affected_skus)} affected products...")
                embeddings_generated = self._generate_embeddings_for_skus(affected_skus)
            
            # Step 10: Record successful sync completion
            sync_end_time = datetime.now(timezone.utc)
            duration = (sync_end_time - sync_start_time).total_seconds()
            
            results = {
                "success": True,
                "products_processed": len(products_df),
                "products_upserted": len(affected_skus),
                "products_deactivated": deactivated_count,
                "embeddings_generated": embeddings_generated,
                "duration_seconds": duration,
                "last_sync_date": sync_end_time.isoformat()
            }
            
            self.logger.info(
                "Products synchronization completed successfully",
                **results
            )
            
            return results
            
        except Exception as e:
            sync_end_time = datetime.now(timezone.utc)
            duration = (sync_end_time - sync_start_time).total_seconds()
            
            self.logger.error(
                "Products synchronization failed",
                error=str(e),
                duration_seconds=duration,
                exc_info=True
            )
            
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": duration
            }
    
    def _map_product_columns(self, df):
        """Map DataFrame columns to database schema."""
        self.logger.info("Mapping product columns to database schema...")
        
        # Column mapping from Odoo fields to database fields
        column_mapping = {
            'default_code': 'sku',
            'categ_id_id': 'category_id',
            'categ_id_name': 'category_name',
            'detailed_type': 'product_type',
            'uom_id_id': 'uom_id',
            'uom_id_name': 'uom_name',
            'write_date': 'last_update'
        }
        
        # Rename columns
        df = df.rename(columns=column_mapping)
        
        # Ensure required columns exist with defaults
        required_columns = {
            'sku': '',
            'name': '',
            'description': None,
            'category_id': None,
            'category_name': None,
            'is_active': True,
            'list_price': 0.0,
            'standard_price': 0.0,
            'product_type': None,
            'barcode': None,
            'weight': 0.0,
            'volume': 0.0,
            'sale_ok': True,
            'purchase_ok': True,
            'uom_id': None,
            'uom_name': None,
            'company_id': None,
            'text_for_embedding': '',
            'last_update': None
        }
        
        for col, default_value in required_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        # Filter out rows without SKU
        initial_count = len(df)
        df = df[df['sku'].notna() & (df['sku'] != '') & (df['sku'] != 'False')]
        final_count = len(df)
        
        if final_count != initial_count:
            self.logger.warning(
                f"Filtered out {initial_count - final_count} products without valid SKU"
            )
        
        # Select only the columns we need for the database
        df = df[list(required_columns.keys())]
        
        self.logger.info(f"Mapped {len(df)} products for database insertion")
        return df
    
    def _generate_embeddings_for_skus(self, skus: List[str]) -> int:
        """
        Generate embeddings for specific SKUs.
        
        Args:
            skus: List of SKUs to generate embeddings for
            
        Returns:
            Number of embeddings successfully generated
        """
        if not skus:
            return 0
        
        try:
            # Get products that need embeddings from the database
            products_needing_embeddings = self.product_updater.get_products_needing_embeddings()
            
            # Filter to only the SKUs we care about
            relevant_products = [
                (sku, text) for sku, text in products_needing_embeddings 
                if sku in skus
            ]
            
            if not relevant_products:
                self.logger.info("No products need embeddings generation")
                return 0
            
            self.logger.info(f"Generating embeddings for {len(relevant_products)} products")
            
            # Extract texts for embedding generation
            texts = [text for _, text in relevant_products]
            skus_list = [sku for sku, _ in relevant_products]
            
            # Generate embeddings
            embeddings = self.embedding_generator.generate(texts)
            
            if len(embeddings) != len(texts):
                self.logger.error(
                    "Mismatch between number of texts and embeddings",
                    texts_count=len(texts),
                    embeddings_count=len(embeddings)
                )
                return 0
            
            # Prepare SKU-embedding pairs
            sku_embeddings = list(zip(skus_list, embeddings))
            
            # Update embeddings in database
            updated_count = self.product_updater.update_embeddings(sku_embeddings)
            
            self.logger.info(f"Successfully generated and stored {updated_count} embeddings")
            return updated_count
            
        except Exception as e:
            self.logger.error("Failed to generate embeddings", error=str(e))
            return 0
    
    def test_connections(self) -> Dict[str, Any]:
        """
        Test all system connections.
        
        Returns:
            Dictionary with connection test results
        """
        self.logger.info("Testing system connections...")
        
        results = {
            "odoo": False,
            "database": False,
            "openai": False
        }
        
        try:
            # Test Odoo connection
            self.logger.info("Testing Odoo connection...")
            odoo_product = OdooProduct(use_test=self.use_test_odoo)
            # Try to read one product to test connection
            test_products = odoo_product.read_products(domain=[])
            results["odoo"] = True
            self.logger.info("Odoo connection successful")
            
        except Exception as e:
            self.logger.error("Odoo connection failed", error=str(e))
        
        try:
            # Test database connection
            self.logger.info("Testing database connection...")
            product_updater = ProductUpdater()
            product_updater.test_connection()
            results["database"] = True
            self.logger.info("Database connection successful")
            
        except Exception as e:
            self.logger.error("Database connection failed", error=str(e))
        
        try:
            # Test OpenAI connection
            self.logger.info("Testing OpenAI connection...")
            embedding_generator = EmbeddingGenerator()
            if embedding_generator.test_connection():
                results["openai"] = True
                self.logger.info("OpenAI connection successful")
            
        except Exception as e:
            self.logger.error("OpenAI connection failed", error=str(e))
        
        all_connected = all(results.values())
        self.logger.info(
            "Connection tests completed",
            all_connected=all_connected,
            **results
        )
        
        return {"all_connected": all_connected, "individual_results": results}
    
    def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up resources...")
        
        try:
            if self.product_updater:
                self.product_updater.close()
        except Exception as e:
            self.logger.error("Error cleaning up product updater", error=str(e))


def main():
    """Main entry point for the products synchronization engine."""
    logger.info("Products Engine starting...")
    
    # Get configuration from environment
    use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
    force_full_sync = os.getenv('FORCE_FULL_SYNC', 'false').lower() == 'true'
    test_connections_only = os.getenv('TEST_CONNECTIONS_ONLY', 'false').lower() == 'true'
    
    logger.info(
        "Configuration loaded",
        use_test_odoo=use_test_odoo,
        force_full_sync=force_full_sync,
        test_connections_only=test_connections_only,
        environment=config.environment
    )
    
    # Create sync manager
    sync_manager = SyncManager(use_test_odoo=use_test_odoo)
    
    try:
        if test_connections_only:
            # Just test connections
            logger.info("Testing connections only...")
            results = sync_manager.test_connections()
            
            if results["all_connected"]:
                logger.info("All connections successful")
                return 0
            else:
                logger.error("Some connections failed", **results["individual_results"])
                return 1
        else:
            # Run full synchronization
            results = sync_manager.run_sync(force_full_sync=force_full_sync)
            
            if results["success"]:
                logger.info("Synchronization completed successfully", **results)
                return 0
            else:
                logger.error("Synchronization failed", **results)
                return 1
    
    except KeyboardInterrupt:
        logger.info("Synchronization interrupted by user")
        return 1
    except Exception as e:
        logger.error("Unexpected error during synchronization", error=str(e), exc_info=True)
        return 1
    finally:
        sync_manager.cleanup()


if __name__ == "__main__":
    import sys
    sys.exit(main()) 