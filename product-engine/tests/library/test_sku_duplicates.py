#!/usr/bin/env python3
"""
Test para verificar el comportamiento de UPSERT con SKUs duplicados.

Este test verifica que:
1. SKUs nuevos se insertan correctamente
2. SKUs existentes se actualizan sin errores  
3. Los datos se actualizan correctamente
4. No se crean registros duplicados
"""

import sys
import pandas as pd
from datetime import datetime


def test_duplicate_sku_behavior():
    """Test principal para verificar comportamiento con SKUs duplicados."""
    print("🔄 INICIANDO TEST DE SKUs DUPLICADOS")
    print("=" * 60)
    
    success = True
    
    # Test 1: Inserción inicial
    if not test_initial_insert():
        success = False
    
    # Test 2: Actualización con mismo SKU
    if not test_duplicate_update():
        success = False
    
    # Test 3: Lote mixto (nuevos + duplicados)
    if not test_mixed_batch():
        success = False
    
    # Test 4: Verificación de integridad
    if not test_data_integrity():
        success = False
    
    # Cleanup
    cleanup_test_data()
    
    return success


def test_initial_insert():
    """Test 1: Inserción inicial de productos."""
    try:
        from db_manager.product_updater import ProductUpdater
        
        print("\n📝 Test 1: Inserción inicial")
        print("-" * 40)
        
        updater = ProductUpdater()
        
        # Crear productos de prueba
        initial_products = pd.DataFrame([
            {
                'sku': 'TEST-DUP-001',
                'name': 'Producto Inicial A',
                'description': 'Descripción inicial A',
                'list_price': 100.00,
                'standard_price': 50.00,
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': True,
                'text_for_embedding': 'Producto Inicial A'
            },
            {
                'sku': 'TEST-DUP-002', 
                'name': 'Producto Inicial B',
                'description': 'Descripción inicial B',
                'list_price': 200.00,
                'standard_price': 100.00,
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': True,
                'text_for_embedding': 'Producto Inicial B'
            }
        ])
        
        # Insertar productos
        affected_skus = updater.upsert_products(initial_products)
        
        print(f"✅ Productos insertados: {len(affected_skus)}")
        print(f"📋 SKUs afectados: {affected_skus}")
        
        # Verificar inserción
        from common.database import database
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT sku, name, list_price 
                FROM products 
                WHERE sku IN ('TEST-DUP-001', 'TEST-DUP-002')
                ORDER BY sku;
            """)
            results = cursor.fetchall()
            
            if len(results) == 2:
                print(f"✅ Verificación: {len(results)} productos encontrados en BD")
                for row in results:
                    print(f"  - {row['sku']}: {row['name']} (${row['list_price']})")
                return True
            else:
                print(f"❌ Error: Se esperaban 2 productos, se encontraron {len(results)}")
                return False
        
    except Exception as e:
        print(f"❌ Error en inserción inicial: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_duplicate_update():
    """Test 2: Actualización con SKUs duplicados."""
    try:
        from db_manager.product_updater import ProductUpdater
        
        print("\n🔄 Test 2: Actualización con SKUs duplicados")
        print("-" * 40)
        
        updater = ProductUpdater()
        
        # Crear productos con SKUs existentes pero datos diferentes
        updated_products = pd.DataFrame([
            {
                'sku': 'TEST-DUP-001',  # SKU existente
                'name': 'Producto ACTUALIZADO A',  # Nombre diferente
                'description': 'Descripción ACTUALIZADA A',  # Descripción diferente
                'list_price': 150.00,  # Precio diferente
                'standard_price': 75.00,  # Precio diferente
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': False,  # Valor diferente
                'text_for_embedding': 'Producto ACTUALIZADO A'
            },
            {
                'sku': 'TEST-DUP-002',  # SKU existente
                'name': 'Producto ACTUALIZADO B',  # Nombre diferente
                'description': 'Descripción ACTUALIZADA B',  # Descripción diferente
                'list_price': 250.00,  # Precio diferente
                'standard_price': 125.00,  # Precio diferente
                'is_active': False,  # Valor diferente
                'sale_ok': False,  # Valor diferente
                'purchase_ok': True,
                'text_for_embedding': 'Producto ACTUALIZADO B'
            }
        ])
        
        # Actualizar productos
        affected_skus = updater.upsert_products(updated_products)
        
        print(f"✅ Productos actualizados: {len(affected_skus)}")
        print(f"📋 SKUs afectados: {affected_skus}")
        
        # Verificar actualización
        from common.database import database
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT sku, name, list_price, is_active, purchase_ok
                FROM products 
                WHERE sku IN ('TEST-DUP-001', 'TEST-DUP-002')
                ORDER BY sku;
            """)
            results = cursor.fetchall()
            
            if len(results) == 2:
                print("✅ Verificación de actualizaciones:")
                
                # Verificar TEST-DUP-001
                row1 = results[0]
                if (row1['name'] == 'Producto ACTUALIZADO A' and 
                    row1['list_price'] == 150.00 and
                    row1['purchase_ok'] == False):
                    print(f"  ✅ {row1['sku']}: Actualizado correctamente")
                else:
                    print(f"  ❌ {row1['sku']}: No se actualizó correctamente")
                    return False
                
                # Verificar TEST-DUP-002
                row2 = results[1]
                if (row2['name'] == 'Producto ACTUALIZADO B' and 
                    row2['list_price'] == 250.00 and
                    row2['is_active'] == False):
                    print(f"  ✅ {row2['sku']}: Actualizado correctamente")
                else:
                    print(f"  ❌ {row2['sku']}: No se actualizó correctamente")
                    return False
                
                return True
            else:
                print(f"❌ Error: Se esperaban 2 productos, se encontraron {len(results)}")
                return False
        
    except Exception as e:
        print(f"❌ Error en actualización: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mixed_batch():
    """Test 3: Lote mixto con productos nuevos y duplicados."""
    try:
        from db_manager.product_updater import ProductUpdater
        
        print("\n📦 Test 3: Lote mixto (nuevos + duplicados)")
        print("-" * 40)
        
        updater = ProductUpdater()
        
        # Crear lote mixto
        mixed_products = pd.DataFrame([
            {
                'sku': 'TEST-DUP-001',  # Existente - se actualizará
                'name': 'Producto FINAL A',
                'list_price': 175.00,
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': True,
                'text_for_embedding': 'Producto FINAL A'
            },
            {
                'sku': 'TEST-DUP-003',  # Nuevo - se insertará
                'name': 'Producto Nuevo C',
                'list_price': 300.00,
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': True,
                'text_for_embedding': 'Producto Nuevo C'
            },
            {
                'sku': 'TEST-DUP-002',  # Existente - se actualizará
                'name': 'Producto FINAL B',
                'list_price': 275.00,
                'is_active': True,
                'sale_ok': True,
                'purchase_ok': True,
                'text_for_embedding': 'Producto FINAL B'
            }
        ])
        
        # Procesar lote mixto
        affected_skus = updater.upsert_products(mixed_products)
        
        print(f"✅ Productos procesados: {len(affected_skus)}")
        print(f"📋 SKUs afectados: {affected_skus}")
        
        # Verificar resultado
        from common.database import database
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM products 
                WHERE sku IN ('TEST-DUP-001', 'TEST-DUP-002', 'TEST-DUP-003');
            """)
            count = cursor.fetchone()['count']
            
            if count == 3:
                print(f"✅ Verificación: {count} productos en BD (correcto)")
                
                # Verificar que no hay duplicados
                cursor.execute("""
                    SELECT sku, COUNT(*) as count
                    FROM products 
                    WHERE sku IN ('TEST-DUP-001', 'TEST-DUP-002', 'TEST-DUP-003')
                    GROUP BY sku
                    HAVING COUNT(*) > 1;
                """)
                duplicates = cursor.fetchall()
                
                if len(duplicates) == 0:
                    print("✅ No hay SKUs duplicados en BD")
                    return True
                else:
                    print(f"❌ Se encontraron SKUs duplicados: {duplicates}")
                    return False
            else:
                print(f"❌ Error: Se esperaban 3 productos, se encontraron {count}")
                return False
        
    except Exception as e:
        print(f"❌ Error en lote mixto: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_integrity():
    """Test 4: Verificación final de integridad."""
    try:
        print("\n🔍 Test 4: Verificación de integridad")
        print("-" * 40)
        
        from common.database import database
        with database.get_cursor(commit=False) as cursor:
            # Verificar que todos los productos de test están presentes
            cursor.execute("""
                SELECT sku, name, list_price, is_active
                FROM products 
                WHERE sku LIKE 'TEST-DUP-%'
                ORDER BY sku;
            """)
            test_products = cursor.fetchall()
            
            print(f"📊 Productos de test encontrados: {len(test_products)}")
            
            for product in test_products:
                print(f"  - {product['sku']}: {product['name']} (${product['list_price']}) [{'Activo' if product['is_active'] else 'Inactivo'}]")
            
            # Verificar que no hay nulos en campos críticos
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM products 
                WHERE sku LIKE 'TEST-DUP-%' 
                AND (sku IS NULL OR name IS NULL OR list_price IS NULL);
            """)
            null_count = cursor.fetchone()['count']
            
            if null_count == 0:
                print("✅ No hay campos nulos en datos críticos")
                return True
            else:
                print(f"❌ Se encontraron {null_count} registros con campos nulos")
                return False
        
    except Exception as e:
        print(f"❌ Error en verificación de integridad: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """Limpiar datos de prueba."""
    try:
        print("\n🧹 Limpiando datos de prueba...")
        
        from common.database import database
        with database.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM products 
                WHERE sku LIKE 'TEST-DUP-%';
            """)
            
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM products 
                WHERE sku LIKE 'TEST-DUP-%';
            """)
            remaining = cursor.fetchone()['count']
            
            if remaining == 0:
                print("✅ Datos de prueba eliminados correctamente")
            else:
                print(f"⚠️ Quedan {remaining} registros de prueba")
        
    except Exception as e:
        print(f"❌ Error en limpieza: {e}")


def main():
    """Función principal del test."""
    print("🔄 INICIANDO TEST DE COMPORTAMIENTO CON SKUs DUPLICADOS")
    print("=" * 60)
    
    success = test_duplicate_sku_behavior()
    
    if success:
        print("\n🎯 ✅ TEST DE SKUs DUPLICADOS COMPLETADO EXITOSAMENTE")
        print("📋 Resumen:")
        print("  ✅ Inserción inicial funcionando")
        print("  ✅ Actualización de duplicados funcionando")
        print("  ✅ Lotes mixtos funcionando")
        print("  ✅ Integridad de datos verificada")
        print("\n🏆 El comportamiento UPSERT funciona correctamente")
        return 0
    else:
        print("\n❌ TEST DE SKUs DUPLICADOS FALLÓ")
        print("💡 Revisa los errores anteriores para identificar problemas")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 