#!/usr/bin/env python3
"""
Test script for product search functionality.

This script demonstrates the hybrid search capabilities:
1. Exact SKU search (highest priority)
2. Semantic embedding search
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from product_engine import search_products
from common.database import database
import json


def test_search_functionality():
    """Test the product search functionality with different queries."""
    
    print("🔍 Testing Product Search Functionality")
    print("=" * 50)
    
    # Test cases
    test_queries = [
        # Exact SKU searches
        ("ACO-100", "Exact SKU search"),
        ("PRO-WHY", "Another exact SKU search"),
        ("INVALID-SKU", "Non-existent SKU"),
        
        # Semantic searches
        ("aceite de coco", "Semantic search for coconut oil"),
        ("proteína", "Semantic search for protein"),
        ("coco 100ml", "Mixed search (product + variant)"),
        ("suplemento", "Generic category search"),
    ]
    
    for query, description in test_queries:
        print(f"\n📋 {description}")
        print(f"Query: '{query}'")
        print("-" * 30)
        
        try:
            results = search_products(query, limit=5)
            
            if not results:
                print("❌ No results found")
                continue
            
            print(f"✅ Found {len(results)} result(s):")
            
            for i, result in enumerate(results, 1):
                search_type = result.get('search_type', 'unknown')
                relevance = result.get('relevance_score', 0)
                
                print(f"  {i}. {result['sku']} - {result['name']}")
                print(f"     Type: {search_type} | Relevance: {relevance:.3f}")
                
                if 'similarity_score' in result:
                    print(f"     Similarity: {result['similarity_score']:.3f}")
                
                if result.get('category_name'):
                    print(f"     Category: {result['category_name']}")
                
                print()
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue


def test_database_connection():
    """Test basic database connection."""
    print("🔗 Testing Database Connection")
    print("=" * 30)
    
    try:
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = true")
            result = cursor.fetchone()
            count = result['count'] if result else 0
            print(f"✅ Connected successfully")
            print(f"📊 Active products in database: {count}")
            
            # Check if we have any embeddings
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE embedding IS NOT NULL AND is_active = true")
            result = cursor.fetchone()
            embedding_count = result['count'] if result else 0
            print(f"🧠 Products with embeddings: {embedding_count}")
            
            if embedding_count == 0:
                print("⚠️  Warning: No products have embeddings yet. Semantic search will not work.")
                print("   Run the product sync to generate embeddings.")
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False
    
    return True


def main():
    """Main test function."""
    print("🚀 Product Engine Search Test")
    print("=" * 50)
    
    # Test database connection first
    if not test_database_connection():
        print("\n❌ Database connection failed. Please check your configuration.")
        return
    
    print("\n" + "=" * 50)
    
    # Test search functionality
    test_search_functionality()
    
    print("\n" + "=" * 50)
    print("🎯 Test completed!")
    print("\nUsage examples:")
    print("  from product_engine import search_products")
    print("  results = search_products('ACO-100')  # Exact SKU")
    print("  results = search_products('aceite de coco')  # Semantic")
    
    print("\nResult format:")
    print("  - sku: Product SKU")
    print("  - name: Product name/variant")
    print("  - search_type: 'exact_sku' or 'semantic'")
    print("  - relevance_score: 0.0 to 1.0 (higher = more relevant)")
    print("  - similarity_score: For semantic results only")


if __name__ == "__main__":
    main() 