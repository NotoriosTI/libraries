"""
Test script for the new modular product engine structure - simplified version.
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_direct_imports():
    """Test direct imports from the modules."""
    print("🧪 Testing direct imports...")
    
    try:
        # Test common modules directly
        from common.config import config
        from common.models import ProductData, SearchResult
        from common.database import database
        print("✅ Common modules imported successfully")
        
        # Test db_client modules directly
        from db_client.product_search import ProductSearchClient
        from db_client.product_reader import ProductReader
        print("✅ DB Client modules imported successfully")
        
        # Test db_manager modules directly
        from db_manager.sync_manager import SyncManager
        from db_manager.product_updater import ProductUpdater
        print("✅ DB Manager modules imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_product_engine_package():
    """Test importing through the product_engine package."""
    print("\n📦 Testing product_engine package...")
    
    try:
        # Test importing the main package
        import product_engine
        print("✅ Product engine package imported")
        
        # Test main functions
        from product_engine import search_products, get_products_count
        print("✅ Main functions available")
        
        # Test count function (should work even with empty DB)
        count = get_products_count()
        print(f"✅ Products count: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Package test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """Test configuration."""
    print("\n⚙️ Testing configuration...")
    
    try:
        from common.config import config
        
        print(f"✅ Environment: {config.environment}")
        print(f"✅ Is development: {config.is_development}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False


def main():
    """Run simplified tests."""
    print("🧪 TESTING NEW MODULAR STRUCTURE (SIMPLIFIED)")
    print("=" * 60)
    
    tests = [
        test_direct_imports,
        test_configuration,
        test_product_engine_package
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📋 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 