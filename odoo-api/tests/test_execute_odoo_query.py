#!/usr/bin/env python3
"""
Test para la función execute_odoo_query de OdooProduct.

Este test verifica que la función execute_odoo_query funcione correctamente
para obtener productos activos usando la nueva función tipada.
"""

import sys
import os
from pprint import pprint
from config_manager import secrets
from odoo_api.product import OdooProduct

print(secrets.ODOO_TEST_DB)
print(secrets.ODOO_TEST_URL)
print(secrets.ODOO_TEST_USERNAME)
print(secrets.ODOO_TEST_PASSWORD)

odoo_product = OdooProduct(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
)

def test_execute_odoo_query_active_products():
    """
    Test para verificar que execute_odoo_query puede obtener productos activos.
    """
    print("🔍 Testing execute_odoo_query - Active Products")
    print("=" * 50)
    
    # Configuración de conexión
    odoo_product = OdooProduct(
        db=secrets.ODOO_TEST_DB,
        url=secrets.ODOO_TEST_URL,
        username=secrets.ODOO_TEST_USERNAME,
        password=secrets.ODOO_TEST_PASSWORD,
    )

    
    try:
        # Dominio para productos activos
        domain = [['active', '=', True]]
        
        # Usar execute_odoo_query para obtener productos activos
        print("Ejecutando query con execute_odoo_query...")
        products = odoo_product.execute_odoo_query(
            model='product.product',
            method='search_read',
            args=[domain],
            kwargs={'fields': ['default_code', 'name', 'active']}
        )
        
        print(f"✅ Query ejecutada exitosamente")
        print(f"📊 Número de productos activos encontrados: {len(products)}")
        
        # Validar la estructura de los resultados
        if products:
            print("\n📋 Primeros 5 productos:")
            for i, product in enumerate(products[:5]):
                print(f"  {i+1}. SKU: {product.get('default_code', 'N/A')} | Nombre: {product.get('name', 'N/A')} | Activo: {product.get('active', 'N/A')}")
            
            # Verificar que todos los productos estén activos
            all_active = all(product.get('active', False) for product in products)
            assert all_active, "Todos los productos deben estar activos"
            print("✅ Todos los productos están activos")
            
            # Verificar que los productos tengan SKU
            products_with_sku = [p for p in products if p.get('default_code')]
            print(f"📦 Productos con SKU: {len(products_with_sku)} de {len(products)}")
            
        else:
            print("⚠️  No se encontraron productos activos")
            
        return True
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_execute_odoo_query_single_product():
    """
    Test para verificar que execute_odoo_query puede obtener un producto específico.
    """
    print("\n🔍 Testing execute_odoo_query - Single Product")
    print("=" * 50)
    
    odoo_product = OdooProduct(
        db=secrets.ODOO_TEST_DB,
        url=secrets.ODOO_TEST_URL,
        username=secrets.ODOO_TEST_USERNAME,
        password=secrets.ODOO_TEST_PASSWORD,
    )

    
    try:
        # Primero obtener un producto activo para usarlo en el test
        products = odoo_product.execute_odoo_query(
            model='product.product',
            method='search_read',
            args=[[['active', '=', True]]],
            kwargs={'fields': ['id', 'default_code'], 'limit': 1}
        )
        
        if not products:
            print("⚠️  No hay productos activos para testear")
            return True
        
        product_id = products[0]['id']
        product_sku = products[0].get('default_code', 'N/A')
        
        print(f"🔍 Obteniendo detalles del producto ID: {product_id} (SKU: {product_sku})")
        
        # Obtener detalles completos del producto
        product_details = odoo_product.execute_odoo_query(
            model='product.product',
            method='read',
            args=[[product_id]],
            kwargs={'fields': ['id', 'default_code', 'name', 'active', 'list_price']}
        )
        
        if product_details:
            product = product_details[0]
            print(f"✅ Producto encontrado:")
            print(f"   ID: {product.get('id')}")
            print(f"   SKU: {product.get('default_code')}")
            print(f"   Nombre: {product.get('name')}")
            print(f"   Activo: {product.get('active')}")
            print(f"   Precio: {product.get('list_price')}")
            
            # Validar que el producto esté activo
            assert product.get('active', False), "El producto debe estar activo"
            print("✅ Producto está activo")
            
        else:
            print("❌ No se pudo obtener detalles del producto")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_execute_odoo_query_count():
    """
    Test para verificar que execute_odoo_query puede contar productos.
    """
    print("\n🔍 Testing execute_odoo_query - Count Products")
    print("=" * 50)
    
    odoo_product = OdooProduct(
        db=secrets.ODOO_TEST_DB,
        url=secrets.ODOO_TEST_URL,
        username=secrets.ODOO_TEST_USERNAME,
        password=secrets.ODOO_TEST_PASSWORD,
    )

    
    try:
        # Contar productos activos
        active_count = odoo_product.execute_odoo_query(
            model='product.product',
            method='search_count',
            args=[[['active', '=', True]]]
        )
        
        print(f"📊 Número de productos activos: {active_count}")
        
        # Contar todos los productos
        total_count = odoo_product.execute_odoo_query(
            model='product.product',
            method='search_count',
            args=[[]]
        )
        
        print(f"📊 Número total de productos: {total_count}")
        
        # Validar que el conteo sea lógico
        assert active_count <= total_count, "Los productos activos no pueden ser más que el total"
        print("✅ Conteo lógico correcto")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal que ejecuta todos los tests."""
    print("🚀 Test de execute_odoo_query")
    print("=" * 60)
    
    tests = [
        test_execute_odoo_query_active_products,
        test_execute_odoo_query_single_product,
        test_execute_odoo_query_count,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_func.__name__} - PASÓ")
            else:
                failed += 1
                print(f"❌ {test_func.__name__} - FALLÓ")
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} - ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"🎯 Resultados del test:")
    print(f"   ✅ Pasados: {passed}")
    print(f"   ❌ Fallidos: {failed}")
    print(f"   📊 Total: {passed + failed}")
    
    if failed == 0:
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        return 0
    else:
        print("🔥 Algunos tests fallaron. Revisa los errores arriba.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
