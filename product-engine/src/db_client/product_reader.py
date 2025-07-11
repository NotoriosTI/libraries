"""
Product reader for simple database read operations.

This module provides basic read operations for product data
that are commonly used as dependencies by other services.
"""
from typing import List, Dict, Any, Optional, Set
import structlog

from common.database import database
from common.models import ProductData

logger = structlog.get_logger(__name__)


class ProductReader:
    """
    Reader for basic product database operations.
    
    This class provides simple read operations that are commonly
    used by other services as dependencies.
    """
    
    def __init__(self):
        """Initialize the product reader."""
        self.logger = logger.bind(component="product_reader")
        self.logger.info("ProductReader initialized")
    
    def get_product_by_sku(self, sku: str) -> Optional[ProductData]:
        """
        Get a single product by SKU.
        
        Args:
            sku: Product SKU to retrieve
            
        Returns:
            ProductData if found, None otherwise
        """
        try:
            result = database.execute_query(
                """
                SELECT sku, name, description, category_id, category_name, is_active,
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at
                FROM products 
                WHERE sku = %s
                """,
                (sku.upper(),),
                fetch_one=True
            )
            
            if result:
                return ProductData.from_db_row(result)
            return None
            
        except Exception as e:
            self.logger.error("Failed to get product by SKU", error=str(e), sku=sku)
            return None
    
    def get_active_products(self, limit: Optional[int] = None) -> List[ProductData]:
        """
        Get all active products.
        
        Args:
            limit: Optional limit on number of products to return
            
        Returns:
            List of ProductData objects for active products
        """
        try:
            query = """
                SELECT sku, name, description, category_id, category_name, is_active,
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at
                FROM products 
                WHERE is_active = true
                ORDER BY name
            """
            
            params = None
            if limit:
                query += " LIMIT %s"
                params = (limit,)
            
            results = database.execute_query(query, params)
            
            return [ProductData.from_db_row(row) for row in (results or [])]
            
        except Exception as e:
            self.logger.error("Failed to get active products", error=str(e), limit=limit)
            return []
    
    def get_products_by_category(self, category_id: int, 
                                active_only: bool = True) -> List[ProductData]:
        """
        Get products by category ID.
        
        Args:
            category_id: Category ID to filter by
            active_only: If True, only return active products
            
        Returns:
            List of ProductData objects in the category
        """
        try:
            query = """
                SELECT sku, name, description, category_id, category_name, is_active,
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at
                FROM products 
                WHERE category_id = %s
            """
            
            params = [category_id]
            if active_only:
                query += " AND is_active = true"
            
            query += " ORDER BY name"
            
            results = database.execute_query(query, tuple(params))
            
            return [ProductData.from_db_row(row) for row in (results or [])]
            
        except Exception as e:
            self.logger.error(
                "Failed to get products by category",
                error=str(e),
                category_id=category_id,
                active_only=active_only
            )
            return []
    
    def get_product_skus(self, active_only: bool = True) -> Set[str]:
        """
        Get all product SKUs.
        
        Args:
            active_only: If True, only return SKUs for active products
            
        Returns:
            Set of product SKUs
        """
        try:
            query = "SELECT sku FROM products"
            params = None
            
            if active_only:
                query += " WHERE is_active = true"
            
            results = database.execute_query(query, params)
            
            return {row['sku'] for row in (results or [])}
            
        except Exception as e:
            self.logger.error("Failed to get product SKUs", error=str(e), active_only=active_only)
            return set()
    
    def get_products_count(self, active_only: bool = True) -> int:
        """
        Get total count of products.
        
        Args:
            active_only: If True, only count active products
            
        Returns:
            Number of products
        """
        try:
            query = "SELECT COUNT(*) as count FROM products"
            params = None
            
            if active_only:
                query += " WHERE is_active = true"
            
            result = database.execute_query(query, params, fetch_one=True)
            
            return result['count'] if result else 0
            
        except Exception as e:
            self.logger.error("Failed to get products count", error=str(e), active_only=active_only)
            return 0
    
    def get_categories(self, active_products_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all product categories.
        
        Args:
            active_products_only: If True, only include categories with active products
            
        Returns:
            List of dictionaries with category information
        """
        try:
            query = """
                SELECT DISTINCT category_id, category_name, COUNT(*) as product_count
                FROM products 
                WHERE category_id IS NOT NULL AND category_name IS NOT NULL
            """
            
            if active_products_only:
                query += " AND is_active = true"
            
            query += " GROUP BY category_id, category_name ORDER BY category_name"
            
            results = database.execute_query(query)
            
            return results or []
            
        except Exception as e:
            self.logger.error(
                "Failed to get categories",
                error=str(e),
                active_products_only=active_products_only
            )
            return []
    
    def get_products_by_skus(self, skus: List[str]) -> List[ProductData]:
        """
        Get multiple products by their SKUs.
        
        Args:
            skus: List of SKUs to retrieve
            
        Returns:
            List of ProductData objects for found products
        """
        if not skus:
            return []
        
        try:
            # Convert SKUs to uppercase for consistency
            upper_skus = [sku.upper() for sku in skus]
            
            # Create placeholder string for IN clause
            placeholders = ','.join(['%s'] * len(upper_skus))
            
            query = f"""
                SELECT sku, name, description, category_id, category_name, is_active,
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at
                FROM products 
                WHERE sku IN ({placeholders})
                ORDER BY name
            """
            
            results = database.execute_query(query, tuple(upper_skus))
            
            return [ProductData.from_db_row(row) for row in (results or [])]
            
        except Exception as e:
            self.logger.error("Failed to get products by SKUs", error=str(e), sku_count=len(skus))
            return []
    
    def product_exists(self, sku: str) -> bool:
        """
        Check if a product exists by SKU.
        
        Args:
            sku: Product SKU to check
            
        Returns:
            True if product exists, False otherwise
        """
        try:
            result = database.execute_query(
                "SELECT 1 FROM products WHERE sku = %s",
                (sku.upper(),),
                fetch_one=True
            )
            
            return result is not None
            
        except Exception as e:
            self.logger.error("Failed to check if product exists", error=str(e), sku=sku)
            return False 