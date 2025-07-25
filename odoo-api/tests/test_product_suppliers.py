#!/usr/bin/env python3
"""
Test script for OdooProduct supplier functionality.

This script tests the supplier-related methods:
1. get_product_suppliers_by_sku - Single SKU
2. get_product_suppliers_by_skus_batch - Multiple SKUs in batch
"""

import sys
import os
import pandas as pd
from pprint import pprint
from odoo_api.product import OdooProduct

# Import config-manager for credentials
from config_manager import secrets
product_api = OdooProduct(
    db=secrets.ODOO_PROD_DB,
    url=secrets.ODOO_PROD_URL,
    username=secrets.ODOO_PROD_USERNAME,
    password=secrets.ODOO_PROD_PASSWORD
)

def test_single_sku_suppliers(sku: str):
    """Test get_product_suppliers_by_sku with a single SKU."""
    print("🔍 Testing Single SKU Suppliers")
    print("=" * 40)
    
    try:
        # Test with a single SKU that likely has suppliers
        result = product_api.get_product_suppliers_by_sku(sku)
        
        print(f"SKU: {sku}")
        print(f"Result type: {type(result)}")
        
        if isinstance(result, pd.DataFrame):
            print(f"DataFrame shape: {result.shape}")
            print(f"Columns: {list(result.columns)}")
            
            if not result.empty:
                print("✅ Suppliers found:")
                print(result[['product_sku', 'product_name', 'supplier_name', 'price', 'currency_symbol']].to_string())
                
                # Validate DataFrame structure
                expected_columns = [
                    'product_id', 'product_sku', 'product_name', 'supplier_id',
                    'supplier_name', 'supplier_vat', 'supplier_code', 'min_qty',
                    'price', 'currency_id', 'currency_name', 'currency_symbol',
                    'delay', 'date_start', 'date_end'
                ]
                
                missing_columns = [col for col in expected_columns if col not in result.columns]
                if missing_columns:
                    print(f"❌ Missing columns: {missing_columns}")
                else:
                    print("✅ DataFrame structure is correct")
                    
                # Validate data types
                assert result['product_sku'].iloc[0] == sku, f"SKU mismatch: expected {sku}, got {result['product_sku'].iloc[0]}"
                print("✅ SKU validation passed")
                
            else:
                print("⚠️  No suppliers found for this SKU")
                
        else:
            print(f"❌ Unexpected result type: {type(result)}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_batch_suppliers(skus: list[str]):
    """Test get_product_suppliers_by_skus_batch with multiple SKUs."""
    print("\n🔍 Testing Batch Suppliers")
    print("=" * 40)
    
    try:
        # Test with multiple SKUs
        result = product_api.get_product_suppliers_by_skus_batch(skus)
        
        print(f"SKUs: {skus}")
        print(f"Result type: {type(result)}")
        
        if isinstance(result, pd.DataFrame):
            print(f"DataFrame shape: {result.shape}")
            print(f"Columns: {list(result.columns)}")
            
            if not result.empty:
                print("✅ Suppliers found:")
                
                # Group by SKU for better display
                for sku in skus:
                    sku_suppliers = result[result['product_sku'] == sku]
                    if not sku_suppliers.empty:
                        print(f"\n📋 SKU: {sku}")
                        print(f"  Product: {sku_suppliers.iloc[0]['product_name']}")
                        print(f"  Suppliers: {len(sku_suppliers)}")
                        for _, supplier in sku_suppliers.iterrows():
                            print(f"    * {supplier['supplier_name']} - {supplier['price']} {supplier['currency_symbol']}")
                    else:
                        print(f"\n📋 SKU: {sku} - No suppliers found")
                
                # Validate batch processing
                unique_skus = result['product_sku'].nunique()
                unique_suppliers = result['supplier_id'].nunique()
                print(f"\n📊 Statistics:")
                print(f"  Unique SKUs with suppliers: {unique_skus}")
                print(f"  Unique suppliers: {unique_suppliers}")
                print(f"  Total supplier records: {len(result)}")
                
            else:
                print("⚠️  No suppliers found for any SKU")
                
        else:
            print(f"❌ Unexpected result type: {type(result)}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_empty_input(skus: list[str]):
    """Test supplier functions with empty input."""
    print("\n🔍 Testing Empty Input")
    print("=" * 40)
    
    try:
        # Test single SKU with empty string
        result = product_api.get_product_suppliers_by_sku("")
        assert isinstance(result, pd.DataFrame), "Should return empty DataFrame"
        assert result.empty, "Should return empty DataFrame for empty SKU"
        print("✅ Empty string SKU handled correctly")
        
        # Test batch with empty list
        result = product_api.get_product_suppliers_by_skus_batch([])
        assert isinstance(result, pd.DataFrame), "Should return empty DataFrame"
        assert result.empty, "Should return empty DataFrame for empty list"
        print("✅ Empty list handled correctly")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_nonexistent_skus(skus: list[str]):
    """Test supplier functions with non-existent SKUs."""
    print("\n🔍 Testing Non-existent SKUs")
    print("=" * 40)
    
    try:
        # Test single non-existent SKU
        result = product_api.get_product_suppliers_by_sku("NONEXISTENT-SKU-12345")
        assert isinstance(result, pd.DataFrame), "Should return DataFrame"
        assert result.empty, "Should return empty DataFrame for non-existent SKU"
        print("✅ Non-existent single SKU handled correctly")
        
        # Test batch with non-existent SKUs
        result = product_api.get_product_suppliers_by_skus_batch(["NONEXISTENT-1", "NONEXISTENT-2"])
        assert isinstance(result, pd.DataFrame), "Should return DataFrame"
        assert result.empty, "Should return empty DataFrame for non-existent SKUs"
        print("✅ Non-existent batch SKUs handled correctly")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_dataframe_structure(skus: list[str]):
    """Test that the returned DataFrame has the correct structure."""
    print("\n🔍 Testing DataFrame Structure")
    print("=" * 40)
    
    try:
        # Get some suppliers to test structure
        result = product_api.get_product_suppliers_by_skus_batch(skus)
        
        if not result.empty:
            # Check required columns
            required_columns = [
                'product_id', 'product_sku', 'product_name', 'supplier_id',
                'supplier_name', 'supplier_vat', 'supplier_code', 'min_qty',
                'price', 'currency_id', 'currency_name', 'currency_symbol',
                'delay', 'date_start', 'date_end'
            ]
            
            missing_columns = [col for col in required_columns if col not in result.columns]
            if missing_columns:
                print(f"❌ Missing columns: {missing_columns}")
            else:
                print("✅ All required columns present")
            
            # Check data types
            print("📊 Data types:")
            for col in result.columns:
                print(f"  {col}: {result[col].dtype}")
            
            # Check for null values in key columns
            key_columns = ['product_sku', 'supplier_name', 'price']
            for col in key_columns:
                if col in result.columns:
                    null_count = result[col].isnull().sum()
                    print(f"  {col} null values: {null_count}")
            
        else:
            print("⚠️  No data to test structure")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_connection():
    """Test basic connection to Odoo."""
    print("🔗 Testing Odoo Connection")
    print("=" * 30)
    
    try:
        if hasattr(product_api, 'models') and product_api.models:
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
    print("🚀 OdooProduct Suppliers Test")
    print("=" * 50)
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without Odoo connection")
        return
    
    # Run all tests
    test_single_sku_suppliers("9290")
    test_batch_suppliers(["ME00011", "ME00012", "MP015", "MP060"])
    test_empty_input([])
    test_nonexistent_skus(["1001", "1002", "1003", "1004"])
    test_dataframe_structure(["ME00011", "ME00012", "MP015", "MP060"])
    
    print("\n✅ All tests completed!")


def debug_proveedor_por_sku_template(odoo_product, sku):
    print(f"\n--- Debug proveedor para SKU (template): {sku} ---")
    # 1. Buscar el producto por SKU en product.product
    product_ids = odoo_product.models.execute_kw(
        odoo_product.db, odoo_product.uid, odoo_product.password,
        'product.product', 'search_read',
        [[['default_code', '=', sku]]],
        {'fields': ['id', 'default_code', 'name', 'product_tmpl_id']}
    )
    if not product_ids:
        print(f"❌ No existe producto con SKU: {sku}")
        return
    product = product_ids[0]
    template_id = product['product_tmpl_id'][0]
    print(f"✅ Producto encontrado: {product['name']} (ID: {product['id']}) - Template ID: {template_id}")

    # 2. Buscar supplierinfo para ese template
    supplierinfo = odoo_product.models.execute_kw(
        odoo_product.db, odoo_product.uid, odoo_product.password,
        'product.supplierinfo', 'search_read',
        [[['product_tmpl_id', '=', template_id]]],
        {'fields': ['partner_id', 'price', 'currency_id']}
    )
    if not supplierinfo:
        print(f"⚠️  El producto no tiene proveedores asociados en product.supplierinfo (por template).")
        return
    print(f"✅ Proveedores encontrados: {len(supplierinfo)}")

    # Obtener todos los partner_ids únicos
    partner_ids = [s['partner_id'][0] for s in supplierinfo if s.get('partner_id') and isinstance(s['partner_id'], list)]
    partners = {}
    if partner_ids:
        partners_data = odoo_product.models.execute_kw(
            odoo_product.db, odoo_product.uid, odoo_product.password,
            'res.partner', 'read',
            [partner_ids],
            {'fields': ['id', 'vat']}
        )
        partners = {p['id']: p.get('vat', '') for p in partners_data}

    for s in supplierinfo:
        partner = s['partner_id']
        partner_str = f"{partner[1]} (ID: {partner[0]})" if isinstance(partner, list) else str(partner)
        rut = partners.get(partner[0], '') if isinstance(partner, list) else ''
        currency = s['currency_id'][1] if s.get('currency_id') and isinstance(s['currency_id'], list) else ''
        print(f"  - Proveedor: {partner_str} | RUT: {rut} | Precio: {s['price']} {currency}")

if __name__ == "__main__":
    main()
    debug_proveedor_por_sku_template(product_api, "MP015") 