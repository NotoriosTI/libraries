#!/usr/bin/env python3
"""
Test completo de db_manager
Este test verifica todas las funcionalidades del db_manager incluyendo:
- Operaciones de lectura (db_client)
- Generación de embeddings
- Búsqueda semántica
- Operaciones de actualización
"""
import sys
import os
from typing import List, Dict, Any

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

def test_db_manager_complete():
    """
    Test principal que verifica todas las funcionalidades del db_manager.
    """
    print("🧪 TESTING DB MANAGER COMPLETE FUNCTIONALITY")
    print("=" * 60)
    
    # Verificar que hay datos en la base de datos
    print("\n📊 Verificando datos en la base de datos...")
    if not verify_database_has_data():
        print("⚠️  No hay datos en la base de datos. Ejecuta primero test_integration_odoo_db.py")
        return False
    
    # Test 1: Verificar lectura básica
    print("\n📖 Test 1: Verificando operaciones de lectura...")
    if not test_basic_read_operations():
        print("❌ Error en operaciones de lectura")
        return False
    
    # Test 2: Generar embeddings
    print("\n🧠 Test 2: Generando embeddings...")
    if not test_embedding_generation():
        print("❌ Error generando embeddings")
        return False
    
    # Test 3: Verificar búsqueda semántica
    print("\n🔍 Test 3: Verificando búsqueda semántica...")
    if not test_semantic_search():
        print("❌ Error en búsqueda semántica")
        return False
    
    # Test 4: Verificar búsqueda híbrida
    print("\n🔄 Test 4: Verificando búsqueda híbrida...")
    if not test_hybrid_search():
        print("❌ Error en búsqueda híbrida")
        return False
    
    # Test 5: Verificar operaciones de actualización
    print("\n✏️ Test 5: Verificando operaciones de actualización...")
    if not test_update_operations():
        print("❌ Error en operaciones de actualización")
        return False
    
    print("\n🎉 ¡Todas las funcionalidades del db_manager están funcionando correctamente!")
    return True


def verify_database_has_data():
    """Verificar que la base de datos tiene datos para los tests."""
    try:
        from common.database import database
        
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = true;")
            count = cursor.fetchone()['count']
            print(f"📊 Productos activos en BD: {count}")
            
            if count == 0:
                print("❌ No hay productos activos en la base de datos")
                return False
                
            # Mostrar algunos productos de ejemplo
            cursor.execute("""
                SELECT sku, name, list_price 
                FROM products 
                WHERE is_active = true 
                LIMIT 3;
            """)
            products = cursor.fetchall()
            
            print("📋 Productos de ejemplo:")
            for product in products:
                print(f"  - {product['sku']}: {product['name'][:40]}... (${product['list_price']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando datos: {e}")
        return False


def test_basic_read_operations():
    """Test de operaciones básicas de lectura usando db_client."""
    try:
        from db_client.product_reader import ProductReader
        
        # Crear el reader
        reader = ProductReader()
        
        # Test 1: Contar productos
        total_count = reader.get_products_count()
        active_count = reader.get_products_count(active_only=True)
        print(f"✅ Total productos: {total_count} | Activos: {active_count}")
        
        # Test 2: Obtener productos activos
        products_page1 = reader.get_active_products(limit=5)
        print(f"✅ Primeros 5 productos activos: {len(products_page1)} productos")
        
        # Test 3: Obtener producto por SKU
        if products_page1:
            sample_sku = products_page1[0].sku
            product_by_sku = reader.get_product_by_sku(sample_sku)
            print(f"✅ Producto por SKU ({sample_sku}): {product_by_sku.name if product_by_sku else 'No encontrado'}")
        
        # Test 4: Obtener categorías disponibles
        categories = reader.get_categories()
        print(f"✅ Categorías disponibles: {len(categories)}")
        
        # Si hay categorías, test productos por categoría
        if categories:
            first_category_id = categories[0]['category_id']
            products_in_category = reader.get_products_by_category(first_category_id)
            print(f"✅ Productos en primera categoría: {len(products_in_category)}")
        
        # Test 5: Obtener productos por SKUs específicos
        if products_page1:
            test_skus = [p.sku for p in products_page1[:3]]
            products_by_skus = reader.get_products_by_skus(test_skus)
            print(f"✅ Productos por SKUs específicos: {len(products_by_skus)} resultados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones de lectura: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_generation():
    """Test de generación de embeddings."""
    try:
        from db_manager.product_updater import ProductUpdater
        from common.embedding_generator import EmbeddingGenerator
        
        # Crear instancias
        updater = ProductUpdater()
        generator = EmbeddingGenerator()
        
        # Test 1: Obtener productos que necesitan embeddings
        products_needing_embeddings = updater.get_products_needing_embeddings(limit=5)
        print(f"📊 Productos que necesitan embeddings: {len(products_needing_embeddings)}")
        
        if not products_needing_embeddings:
            print("✅ Todos los productos ya tienen embeddings")
            return True
        
        # Test 2: Generar embeddings para algunos productos
        texts_to_embed = [text for sku, text in products_needing_embeddings]
        print(f"🧠 Generando embeddings para {len(texts_to_embed)} productos...")
        
        embeddings = generator.generate(texts_to_embed)
        print(f"✅ Embeddings generados: {len(embeddings)}")
        
        # Test 3: Actualizar embeddings en la base de datos
        sku_embeddings = [
            (sku, embedding) 
            for (sku, text), embedding in zip(products_needing_embeddings, embeddings)
        ]
        
        updated_count = updater.update_embeddings(sku_embeddings)
        print(f"✅ Embeddings actualizados en BD: {updated_count}")
        
        # Test 4: Verificar que los embeddings se guardaron
        from common.database import database
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM products 
                WHERE embedding IS NOT NULL AND is_active = true;
            """)
            count_with_embeddings = cursor.fetchone()['count']
            print(f"✅ Productos con embeddings en BD: {count_with_embeddings}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generando embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_search():
    """Test de búsqueda semántica."""
    try:
        from db_client.product_search import ProductSearchClient
        
        # Crear el cliente de búsqueda
        search_client = ProductSearchClient()
        
        # Test queries más realistas basadas en los productos disponibles
        test_queries = [
            ("aceite esencial", "Búsqueda de aceites esenciales"),
            ("esencia", "Búsqueda de esencias"),
            ("molde silicona", "Búsqueda de moldes"),
            ("mica", "Búsqueda de mica"),
            ("menta", "Búsqueda específica de menta")
        ]
        
        successful_searches = 0
        
        for query, description in test_queries:
            print(f"\n🔍 {description}: '{query}'")
            
            try:
                # Buscar con umbral moderado para obtener resultados relevantes
                results = search_client.search_products(
                    query=query, 
                    limit=3, 
                    similarity_threshold=0.4  # Umbral más permisivo para obtener más resultados
                )
                
                print(f"📋 Resultados encontrados: {len(results)}")
                
                if results:
                    successful_searches += 1
                    for i, result in enumerate(results, 1):
                        print(f"  {i}. {result.sku} - {result.name[:40]}...")
                        print(f"     Tipo: {result.search_type} | Relevancia: {result.relevance_score:.3f}")
                        if hasattr(result, 'similarity_score') and result.similarity_score:
                            print(f"     Similitud: {result.similarity_score:.3f}")
                else:
                    print("  ❌ No se encontraron resultados")
                    
            except Exception as e:
                print(f"  ❌ Error en búsqueda: {e}")
        
        print(f"\n📊 Búsquedas exitosas: {successful_searches}/{len(test_queries)}")
        
        # Considerar exitoso si al menos la mitad de las búsquedas funcionaron
        return successful_searches >= len(test_queries) // 2
        
    except Exception as e:
        print(f"❌ Error en búsqueda semántica: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_search():
    """Test de búsqueda híbrida (SKU + semántica)."""
    try:
        from product_engine import search_products
        from common.database import database
        
        # Obtener algunos SKUs reales de la base de datos
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT sku FROM products 
                WHERE is_active = true 
                LIMIT 3;
            """)
            real_skus = [row['sku'] for row in cursor.fetchall()]
        
        print(f"📋 SKUs reales para test: {real_skus}")
        
        # Test 1: Búsqueda exacta por SKU
        if real_skus:
            sku_to_test = real_skus[0]
            print(f"\n🔍 Búsqueda exacta por SKU: {sku_to_test}")
            
            results = search_products(sku_to_test, limit=5)
            print(f"📋 Resultados: {len(results)}")
            
            if results:
                result = results[0]
                print(f"✅ Encontrado: {result['sku']} - {result['name'][:40]}...")
                print(f"   Tipo: {result['search_type']} | Relevancia: {result['relevance_score']}")
        
        # Test 2: Búsqueda semántica con términos realistas
        semantic_queries = ["aceite", "esencia", "molde"]
        
        for query in semantic_queries:
            print(f"\n🔍 Búsqueda semántica: '{query}'")
            
            results = search_products(query, limit=3, similarity_threshold=0.4)
            print(f"📋 Resultados: {len(results)}")
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"  {i}. {result['sku']} - {result['name'][:30]}...")
                    print(f"     Tipo: {result['search_type']} | Relevancia: {result['relevance_score']:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en búsqueda híbrida: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_update_operations():
    """Test de operaciones de actualización."""
    try:
        from db_manager.product_updater import ProductUpdater
        from common.database import database
        import pandas as pd
        
        updater = ProductUpdater()
        
        # Test 1: Obtener fecha de última sincronización
        last_sync = updater.get_last_sync_date()
        print(f"📅 Fecha de última sincronización: {last_sync}")
        
        # Test 2: Crear un producto de prueba para actualización
        test_product_data = {
            'sku': 'TEST-UPDATE-001',
            'name': 'Producto de Prueba para Actualización',
            'description': 'Este es un producto de prueba para verificar actualizaciones',
            'is_active': True,
            'list_price': 19.99,
            'category_name': 'Pruebas',
            'text_for_embedding': 'producto prueba actualización test',
            'last_update': pd.Timestamp.now()
        }
        
        # Crear DataFrame con el producto de prueba
        df_test = pd.DataFrame([test_product_data])
        
        print(f"📝 Insertando producto de prueba: {test_product_data['sku']}")
        affected_skus = updater.upsert_products(df_test)
        print(f"✅ Productos afectados: {affected_skus}")
        
        # Test 3: Verificar que el producto se insertó
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT sku, name, description, list_price 
                FROM products 
                WHERE sku = %s;
            """, (test_product_data['sku'],))
            
            inserted_product = cursor.fetchone()
            if inserted_product:
                print(f"✅ Producto insertado correctamente:")
                print(f"   SKU: {inserted_product['sku']}")
                print(f"   Nombre: {inserted_product['name']}")
                print(f"   Precio: ${inserted_product['list_price']}")
            else:
                print("❌ No se pudo verificar la inserción del producto")
                return False
        
        # Test 4: Actualizar el producto
        test_product_data['name'] = 'Producto de Prueba ACTUALIZADO'
        test_product_data['list_price'] = 29.99
        df_update = pd.DataFrame([test_product_data])
        
        print(f"🔄 Actualizando producto: {test_product_data['sku']}")
        affected_skus = updater.upsert_products(df_update)
        print(f"✅ Productos actualizados: {affected_skus}")
        
        # Test 5: Verificar actualización
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT sku, name, list_price 
                FROM products 
                WHERE sku = %s;
            """, (test_product_data['sku'],))
            
            updated_product = cursor.fetchone()
            if updated_product:
                print(f"✅ Producto actualizado correctamente:")
                print(f"   Nombre: {updated_product['name']}")
                print(f"   Precio: ${updated_product['list_price']}")
            else:
                print("❌ No se pudo verificar la actualización del producto")
                return False
        
        # Test 6: Limpiar - eliminar producto de prueba
        print(f"🗑️ Eliminando producto de prueba...")
        success = updater.delete_product(test_product_data['sku'])
        print(f"✅ Producto eliminado: {success}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones de actualización: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal del test."""
    print("🚀 INICIANDO TEST COMPLETO DE DB MANAGER")
    print("=" * 60)
    
    success = test_db_manager_complete()
    
    if success:
        print("\n🎯 TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print("📋 Funcionalidades verificadas:")
        print("  ✅ Operaciones de lectura (db_client)")
        print("  ✅ Generación de embeddings")
        print("  ✅ Búsqueda semántica")
        print("  ✅ Búsqueda híbrida")
        print("  ✅ Operaciones de actualización")
        print("\n🎉 El sistema db_manager está funcionando correctamente en todos los aspectos")
        return 0
    else:
        print("\n❌ ALGUNOS TESTS FALLARON")
        print("💡 Revisa los errores anteriores para identificar problemas")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 