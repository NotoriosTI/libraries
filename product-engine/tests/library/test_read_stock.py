from product_engine import search_products
from odoo_api import OdooWarehouse
from config_manager import secrets

def test_search_functionality():
    """Test the product search functionality with different queries."""
    
    print("🔍 Testing Product Search Functionality with Batch Stock Processing")
    print("=" * 70)
    
    odoo_db = secrets.ODOO_PROD_DB
    odoo_user = secrets.ODOO_PROD_USERNAME
    odoo_password = secrets.ODOO_PROD_PASSWORD
    odoo_url = secrets.ODOO_PROD_URL
    warehouse = OdooWarehouse(db=odoo_db, url=odoo_url, username=odoo_user, password=odoo_password)
    
    # Test cases
    test_queries = [
        ("aceite de lavanda", "Semantic search for lavender oil"),
        ("aceite de coco", "Semantic search for coconut oil"),
        ("aceite de argán", "Semantic search for argan oil"),
        ("6256", "Exact SKU search for 6256"),
        ("8085", "Exact SKU search for 8085"),
    ]
    
    for query, description in test_queries:
        print(f"\n📋 {description}")
        print(f"Query: '{query}'")
        print("-" * 50)
        
        try:
            results = search_products(query, limit=20, similarity_threshold=0.6)
            
            if not results:
                print("❌ No results found")
                continue
            
            print(f"✅ Found {len(results)} result(s):")
            
            # Debug: Show what search_products returned
            print(f"🔍 Debug - First result from search_products:")
            if results:
                first_result = results[0]
                print(f"  SKU: {first_result.get('sku', 'N/A')}")
                print(f"  Name: {first_result.get('name', 'N/A')}")
                print(f"  Search Type: {first_result.get('search_type', 'N/A')}")
                print(f"  Relevance Score: {first_result.get('relevance_score', 'N/A')}")
                print(f"  All keys: {list(first_result.keys())}")
            
            # Extract all SKUs for batch processing
            skus = [result['sku'] for result in results]
            print(f"🔄 Processing {len(skus)} SKUs in batch: {skus}")
            
            # Get stock information for all SKUs in a single batch call
            stock_batch = warehouse.get_stock_by_sku(skus)
            
            print(f"📦 Batch stock results:")
            for i, result in enumerate(results, 1):
                sku = result['sku']
                stock_info = stock_batch.get(sku, {})
                
                print(f"\n=== Product {i} ===")
                # Try to get name from search result first, then from stock info
                product_name = result.get('name', stock_info.get('product_name', 'N/A'))
                print(f"Name: {product_name}")
                print(f"SKU: {sku}")
                print(f"Category: {result.get('category_name', 'N/A')}")
                print(f"Stock Available: {stock_info.get('qty_available', 0)}")
                print(f"Stock Virtual: {stock_info.get('virtual_available', 0)}")
                
                # Show locations if available
                locations = stock_info.get('locations', [])
                if locations:
                    print(f"Locations ({len(locations)}):")
                    for loc in locations:
                        print(f"  - {loc['location']}: {loc['available']} available")
                else:
                    print("Locations: None")
                    
                print(f"Found: {stock_info.get('found', False)}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue

def test_batch_vs_individual():
    """Compare batch processing vs individual calls performance."""
    print("\n🔍 Testing Batch vs Individual Processing")
    print("=" * 50)
    
    odoo_db = secrets.ODOO_PROD_DB
    odoo_user = secrets.ODOO_PROD_USERNAME
    odoo_password = secrets.ODOO_PROD_PASSWORD
    odoo_url = secrets.ODOO_PROD_URL
    warehouse = OdooWarehouse(db=odoo_db, url=odoo_url, username=odoo_user, password=odoo_password)
    
    # Test with a specific query
    query = "aceite"
    results = search_products(query, limit=20, similarity_threshold=0.6)
    
    if not results:
        print("❌ No results found for comparison")
        return
    
    skus = [result['sku'] for result in results]
    print(f"Testing with SKUs: {skus}")
    
    # Test batch processing
    print("\n📦 Batch Processing:")
    import time
    start_time = time.time()
    batch_results = warehouse.get_stock_by_sku(skus)
    batch_time = time.time() - start_time
    print(f"✅ Batch processing completed in {batch_time:.3f} seconds")
    
    # Test individual processing
    print("\n📦 Individual Processing:")
    start_time = time.time()
    individual_results = {}
    for sku in skus:
        individual_results[sku] = warehouse.get_stock_by_sku(sku)
    individual_time = time.time() - start_time
    print(f"✅ Individual processing completed in {individual_time:.3f} seconds")
    
    # Compare results
    print(f"\n📊 Performance Comparison:")
    print(f"Batch time: {batch_time:.3f}s")
    print(f"Individual time: {individual_time:.3f}s")
    print(f"Speed improvement: {individual_time/batch_time:.1f}x faster")
    
    # Verify results are identical
    results_match = batch_results == individual_results
    print(f"Results identical: {'✅ Yes' if results_match else '❌ No'}")

if __name__ == '__main__':
    test_search_functionality()
    test_batch_vs_individual()