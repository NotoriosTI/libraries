#!/usr/bin/env python3
"""
Test script for OdooWarehouse stock functionality.

This script tests the get_stock_by_sku method with different input types:
1. Single SKU (string)
2. List with single SKU
3. List with multiple SKUs
"""

import sys
import os
from pprint import pprint

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import config-manager for credentials
try:
    from config_manager import Settings
    CONFIG_AVAILABLE = True
except ImportError:
    print("⚠️  config-manager not available, using environment variables")
    CONFIG_AVAILABLE = False

from odoo_api.warehouses import OdooWarehouse

config = Settings()
odoo_config = config.get_odoo_config(use_test=False)
warehouse = OdooWarehouse(
    db=odoo_config['db'],
    url=odoo_config['url'],
    username=odoo_config['username'],
    password=odoo_config['password']
)

def test_single_sku():
    """Test get_stock_by_sku with a single SKU string."""
    print("🔍 Testing Single SKU (string)")
    print("=" * 40)
    
    try:
        # Test with a single SKU
        sku = "8086"  # Using provided SKU
        result = warehouse.get_stock_by_sku(sku)
        
        print(f"SKU: {sku}")
        print(f"Result type: {type(result)}")
        print("Result:")
        pprint(result)
        
        # Validate result structure
        if isinstance(result, dict):
            expected_keys = ["qty_available", "virtual_available", "locations", "product_name", "sku", "found"]
            missing_keys = [key for key in expected_keys if key not in result]
            
            if missing_keys:
                print(f"❌ Missing keys: {missing_keys}")
            else:
                print("✅ Result structure is correct")
                
            if result.get("found"):
                print(f"✅ Product found: {result.get('product_name')}")
                print(f"📦 Available quantity: {result.get('qty_available')}")
                print(f"📦 Virtual quantity: {result.get('virtual_available')}")
                print(f"📍 Locations: {len(result.get('locations', []))}")
            else:
                print("⚠️  Product not found")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_list_single_sku():
    """Test get_stock_by_sku with a list containing a single SKU."""
    print("\n🔍 Testing List with Single SKU")
    print("=" * 40)
    
    try:
        # Test with a list containing one SKU
        sku_list = ["6211"]  # Using provided SKU
        result = warehouse.get_stock_by_sku(sku_list)
        
        print(f"SKU List: {sku_list}")
        print(f"Result type: {type(result)}")
        print("Result:")
        pprint(result)
        
        # Validate that it returns the same structure as single SKU
        if isinstance(result, dict):
            expected_keys = ["qty_available", "virtual_available", "locations", "product_name", "sku", "found"]
            missing_keys = [key for key in expected_keys if key not in result]
            
            if missing_keys:
                print(f"❌ Missing keys: {missing_keys}")
            else:
                print("✅ Result structure is correct (same as single SKU)")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_list_multiple_skus():
    """Test get_stock_by_sku with a list containing multiple SKUs."""
    print("\n🔍 Testing List with Multiple SKUs")
    print("=" * 40)
    
    try:
        # Test with multiple SKUs using provided SKUs
        sku_list = ["8086", "6211", "6009", "6995", "1234"]
        result = warehouse.get_stock_by_sku(sku_list)
        
        print(f"SKU List: {sku_list}")
        print(f"Result type: {type(result)}")
        print("Result:")
        pprint(result)
        
        # Validate result structure for batch processing
        if isinstance(result, dict):
            print(f"✅ Number of results: {len(result)}")
            
            for sku, sku_result in result.items():
                print(f"\n📋 SKU: {sku}")
                if isinstance(sku_result, dict):
                    if sku_result.get("found"):
                        print(f"  ✅ Found: {sku_result.get('product_name')}")
                        print(f"  📦 Available: {sku_result.get('qty_available')}")
                        print(f"  📦 Virtual: {sku_result.get('virtual_available')}")
                    else:
                        print(f"  ❌ Not found")
                else:
                    print(f"  ⚠️  Unexpected result type: {type(sku_result)}")
                    
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_invalid_input():
    """Test get_stock_by_sku with invalid input types."""
    print("\n🔍 Testing Invalid Input")
    print("=" * 40)
    
    try:
        # Test with None
        try:
            result = warehouse.get_stock_by_sku(None)
            print("❌ Should have raised ValueError for None")
        except ValueError as e:
            print(f"✅ Correctly raised ValueError: {e}")
        
        # Test with empty list
        try:
            result = warehouse.get_stock_by_sku([])
            print("❌ Should have raised ValueError for empty list")
        except ValueError as e:
            print(f"✅ Correctly raised ValueError: {e}")
        
        # Test with non-string/non-list
        try:
            result = warehouse.get_stock_by_sku(123)
            print("❌ Should have raised ValueError for integer")
        except ValueError as e:
            print(f"✅ Correctly raised ValueError: {e}")
            
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


def test_connection():
    """Test basic connection to Odoo."""
    print("🔗 Testing Odoo Connection")
    print("=" * 30)
    
    try:
        # Test basic API connection
        warehouse = OdooWarehouse(
            db=odoo_config['db'],
            url=odoo_config['url'],
            username=odoo_config['username'],
            password=odoo_config['password']
        )
        
        if hasattr(warehouse, 'models') and warehouse.models:
            print("✅ Odoo connection successful")
            return True
        else:
            print("❌ Odoo connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False


def main():
    """Main test function."""
    print("🚀 OdooWarehouse Stock Test")
    print("=" * 50)
    
    # Test connection first
    if not test_connection():
        print("\n❌ Cannot proceed without Odoo connection.")
        return
    
    print("\n" + "=" * 50)
    
    # Run all tests
    test_single_sku()
    test_list_single_sku()
    test_list_multiple_skus()
    test_invalid_input()
    
    print("\n" + "=" * 50)
    print("🎯 Test completed!")
    print("\nUsage examples:")
    print("  # Single SKU")
    print("  result = warehouse.get_stock_by_sku('8086')")
    print("  ")
    print("  # List with single SKU (same result as single)")
    print("  result = warehouse.get_stock_by_sku(['6211'])")
    print("  ")
    print("  # Multiple SKUs")
    print("  result = warehouse.get_stock_by_sku(['8086', '6211', '6009', '6995', '1234'])")
    
    print("\nExpected result formats:")
    print("  Single SKU: {'qty_available': 10, 'virtual_available': 15, ...}")
    print("  Multiple SKUs: {'8086': {...}, '6211': {...}}")


if __name__ == "__main__":
    main() 