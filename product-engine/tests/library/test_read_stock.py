from product_engine import search_products
from odoo_api import OdooWarehouse
from config_manager import secrets

def test_search_functionality():
    """Test the product search functionality with different queries."""
    
    print("🔍 Testing Product Search Functionality")
    print("=" * 50)
    
    odoo_db = secrets.ODOO_PROD_DB
    odoo_user = secrets.ODOO_PROD_USERNAME
    odoo_password = secrets.ODOO_PROD_PASSWORD
    odoo_url = secrets.ODOO_PROD_URL
    warehouse = OdooWarehouse(db=odoo_db, url=odoo_url, username=odoo_user, password=odoo_password)
    # Test cases
    test_queries = [
        ("aceite de lavanda", "Semantic search for argan oil"),
    ]
    
    for query, description in test_queries:
        print(f"\n📋 {description}")
        print(f"Query: '{query}'")
        print("-" * 30)
        
        try:
            results = search_products(query, limit=None, similarity_threshold=0.5)
            
            if not results:
                print("❌ No results found")
                continue
            
            print(f"✅ Found {len(results)} result(s):")
            
            for i, result in enumerate(results, 1):
                sku = result['sku']
                stock = warehouse.get_stock_by_sku(sku)
                print(f"=== {i} ===")
                print(f"Name: {stock['product_name']}")
                print(f"SKU: {sku}")
                print(f"Category: {result['category_name']}")
                print(f"Stock: {stock['qty_available']}", end="\n\n")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue

if __name__ == '__main__':
    test_search_functionality()