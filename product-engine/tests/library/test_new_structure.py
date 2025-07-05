"""
Test script for the new modular product engine structure.

This script tests all major components of the reorganized product engine
to ensure they work correctly with the new architecture.
"""
import sys
from pathlib import Path

# Add src to path so we can import the modules
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that all modules can be imported correctly."""
    print("🧪 Testing imports...")
    
    try:
        # Test common modules
        from common.config import config
        from common.models import ProductData, SearchResult
        from common.embedding_generator import EmbeddingGenerator
        from common.database import database
        print("✅ Common modules imported successfully")
        
        # Test db_client modules
        from db_client.product_search import ProductSearchClient
        from db_client.product_reader import ProductReader
        print("✅ DB Client modules imported successfully")
        
        # Test db_manager modules
        from db_manager.sync_manager import SyncManager
        from db_manager.product_updater import ProductUpdater
        print("✅ DB Manager modules imported successfully")
        
        # Test main package
        from product_engine import (
            search_products, get_product_by_sku, get_products_count,
            ProductSearchClient, ProductReader, SyncManager, ProductUpdater
        )
        print("✅ Main package imports successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_configuration():
    """Test configuration loading."""
    print("\n⚙️ Testing configuration...")
    
    try:
        from common.config import config
        
        print(f"✅ Environment: {config.environment}")
        print(f"✅ Is production: {config.is_production}")
        print(f"✅ Is development: {config.is_development}")
        
        # Test configuration methods
        db_config = config.get_database_config()
        print(f"✅ Database config loaded: {db_config['host']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_models():
    """Test data models."""
    print("\n📊 Testing data models...")
    
    try:
        from common.models import ProductData, SearchResult
        from datetime import datetime
        
        # Test ProductData
        product = ProductData(
            sku="TEST-001",
            name="Test Product",
            description="A test product",
            is_active=True,
            list_price=10.99
        )
        
        # Test conversion methods
        product_dict = product.to_dict()
        print(f"✅ ProductData created: {product.sku}")
        
        # Test SearchResult
        search_result = SearchResult.from_product_data(
            product,
            search_type="test",
            relevance_score=0.95
        )
        
        result_dict = search_result.to_dict()
        print(f"✅ SearchResult created: {search_result.search_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False


def test_database_connection():
    """Test database connection."""
    print("\n🔗 Testing database connection...")
    
    try:
        from common.database import database
        
        # Test connection
        if database.test_connection():
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False


def test_components():
    """Test that components can be instantiated."""
    print("\n🔧 Testing component instantiation...")
    
    try:
        # Test db_client components
        from db_client.product_search import ProductSearchClient
        from db_client.product_reader import ProductReader
        
        search_client = ProductSearchClient()
        product_reader = ProductReader()
        print("✅ DB Client components instantiated")
        
        # Test db_manager components  
        from db_manager.product_updater import ProductUpdater
        from db_manager.sync_manager import SyncManager
        
        product_updater = ProductUpdater()
        sync_manager = SyncManager()
        print("✅ DB Manager components instantiated")
        
        return True
        
    except Exception as e:
        print(f"❌ Component instantiation failed: {e}")
        return False


def test_public_api():
    """Test public API functions."""
    print("\n🔌 Testing public API...")
    
    try:
        from product_engine import (
            search_products, get_product_by_sku, get_products_count,
            get_search_client, get_product_reader
        )
        
        # Test that functions exist and are callable
        search_client = get_search_client()
        product_reader = get_product_reader()
        print("✅ Public API functions available")
        
        # Test products count (this should work even with empty database)
        count = get_products_count()
        print(f"✅ Products count: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Public API test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 TESTING NEW MODULAR STRUCTURE")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_configuration,
        test_models,
        test_database_connection,
        test_components,
        test_public_api
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📋 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! New structure is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 