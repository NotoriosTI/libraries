"""
Product search client for hybrid search functionality.

This module provides search capabilities combining exact SKU matches
and semantic embedding search for the product database.
"""
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
import structlog

from common.database import database
from common.embedding_generator import EmbeddingGenerator
from common.models import SearchResult

logger = structlog.get_logger(__name__)


class ProductSearchClient:
    """
    Client for searching products using hybrid approach: exact SKU + semantic search.
    
    This class handles all read operations for product search, including:
    - Exact SKU matching
    - Semantic similarity search using embeddings
    - Hybrid search combining both approaches
    """
    
    def __init__(self):
        """Initialize the product search client."""
        self.logger = logger.bind(component="product_search_client")
        self.embedding_generator = EmbeddingGenerator()
        
        self.logger.info("ProductSearchClient initialized")
    
    def search_products(self, query: str, limit: int = 20, 
                       similarity_threshold: float = 0.8) -> List[SearchResult]:
        """
        Search products using hybrid approach: exact SKU + semantic embedding search.
        
        Args:
            query: Search query (can be SKU or product name/description)
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score for semantic search (0.0-1.0)
            
        Returns:
            List of SearchResult objects ranked by relevance
        """
        self.logger.info(
            "Searching products with query",
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        
        try:
            with database.get_cursor(commit=False) as cursor:
                return self._hybrid_search(cursor, query.strip(), limit, similarity_threshold)
                    
        except Exception as e:
            self.logger.error("Failed to search products", error=str(e), query=query)
            return []
    
    def _hybrid_search(self, cursor, query: str, limit: int, 
                      similarity_threshold: float) -> List[SearchResult]:
        """
        Perform hybrid search combining exact SKU and semantic embedding search.
        
        Args:
            cursor: Database cursor
            query: Clean search query
            limit: Maximum results
            similarity_threshold: Minimum similarity score for semantic search
            
        Returns:
            List of ranked SearchResult objects
        """
        results = []
        query_upper = query.upper()
        
        # STEP 1: Exact SKU search (highest priority)
        exact_sku_result = self._search_exact_sku(cursor, query_upper)
        if exact_sku_result:
            search_result = SearchResult.from_db_row(
                exact_sku_result,
                search_type='exact_sku',
                relevance_score=1.0
            )
            results.append(search_result)
            
            # If exact SKU match found, return immediately with high confidence
            self.logger.info("Found exact SKU match", sku=exact_sku_result['sku'])
            return results
        
        # STEP 2: Semantic embedding search
        remaining_limit = limit - len(results)
        if remaining_limit > 0:
            semantic_results = self._search_by_embedding(
                cursor, query, remaining_limit, similarity_threshold
            )
            for result in semantic_results:
                # Avoid duplicates (shouldn't happen but good to be safe)
                if not any(r.sku == result['sku'] for r in results):
                    search_result = SearchResult.from_db_row(
                        result,
                        search_type='semantic',
                        relevance_score=result.get('similarity_score', 0.5),
                        similarity_score=result.get('similarity_score')
                    )
                    results.append(search_result)
        
        # STEP 3: Sort by relevance score (exact SKU first, then by similarity)
        results.sort(key=lambda x: (
            0 if x.search_type == 'exact_sku' else 1,  # SKU matches first
            -x.relevance_score  # Then by relevance score descending
        ))
        
        self.logger.info(
            "Hybrid search completed",
            total_results=len(results),
            exact_sku_matches=sum(1 for r in results if r.search_type == 'exact_sku'),
            semantic_matches=sum(1 for r in results if r.search_type == 'semantic')
        )
        
        return results[:limit]
    
    def _search_exact_sku(self, cursor, sku: str) -> Optional[Dict[str, Any]]:
        """
        Search for product by exact SKU match.
        
        Args:
            cursor: Database cursor
            sku: SKU to search for (should be uppercase)
            
        Returns:
            Product dictionary if found, None otherwise
        """
        try:
            cursor.execute("""
                SELECT sku, name, description, category_id, category_name, is_active, 
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at
                FROM products 
                WHERE sku = %s AND is_active = true
            """, (sku,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
            
        except Exception as e:
            self.logger.error("Failed to search by exact SKU", error=str(e), sku=sku)
            return None
    
    def _search_by_embedding(self, cursor, query: str, limit: int, 
                           similarity_threshold: float) -> List[Dict[str, Any]]:
        """
        Search products by semantic similarity using embeddings.
        
        Args:
            cursor: Database cursor
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score for results
            
        Returns:
            List of product dictionaries with similarity scores above threshold
        """
        try:
            # First, generate embedding for the query
            query_embedding = self._generate_query_embedding(query)
            if not query_embedding:
                self.logger.warning("Could not generate embedding for query", query=query)
                return []
            
            # Search using vector similarity with threshold filter
            cursor.execute("""
                SELECT sku, name, description, category_id, category_name, is_active,
                       list_price, standard_price, product_type, barcode, weight, volume,
                       sale_ok, purchase_ok, uom_id, uom_name, company_id,
                       text_for_embedding, last_update, created_at, updated_at,
                       (embedding <=> %s::vector) as distance,
                       (1 - (embedding <=> %s::vector)) as similarity_score
                FROM products 
                WHERE embedding IS NOT NULL 
                  AND is_active = true
                  AND (1 - (embedding <=> %s::vector)) > %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, query_embedding, 
                 similarity_threshold, query_embedding, limit))
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # Convert distance to a more intuitive similarity score (0-1)
                result['similarity_score'] = max(0.0, min(1.0, result['similarity_score']))
                results.append(result)
            
            self.logger.info(
                f"Found {len(results)} products with similarity > {similarity_threshold}",
                query=query
            )
            return results
            
        except Exception as e:
            self.logger.error("Failed to search by embedding", error=str(e), query=query)
            return []
    
    def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding for search query using OpenAI API.
        
        Args:
            query: Search query text
            
        Returns:
            Embedding vector as list of floats, or None if failed
        """
        try:
            embeddings = self.embedding_generator.generate([query])
            
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to generate query embedding", error=str(e), query=query)
            return None
    
    def search_by_sku(self, sku: str) -> Optional[SearchResult]:
        """
        Search for a single product by exact SKU.
        
        Args:
            sku: Product SKU to search for
            
        Returns:
            SearchResult if found, None otherwise
        """
        try:
            with database.get_cursor(commit=False) as cursor:
                result = self._search_exact_sku(cursor, sku.upper())
                if result:
                    return SearchResult.from_db_row(
                        result,
                        search_type='exact_sku',
                        relevance_score=1.0
                    )
                return None
                
        except Exception as e:
            self.logger.error("Failed to search by SKU", error=str(e), sku=sku)
            return None
    
    def search_similar(self, query: str, limit: int = 10, 
                      similarity_threshold: float = 0.8) -> List[SearchResult]:
        """
        Search for products by semantic similarity only (no exact SKU matching).
        
        Args:
            query: Search query text
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of SearchResult objects ranked by similarity
        """
        try:
            with database.get_cursor(commit=False) as cursor:
                semantic_results = self._search_by_embedding(
                    cursor, query, limit, similarity_threshold
                )
                
                results = []
                for result in semantic_results:
                    search_result = SearchResult.from_db_row(
                        result,
                        search_type='semantic',
                        relevance_score=result.get('similarity_score', 0.5),
                        similarity_score=result.get('similarity_score')
                    )
                    results.append(search_result)
                
                return results
                
        except Exception as e:
            self.logger.error("Failed to search similar products", error=str(e), query=query)
            return [] 