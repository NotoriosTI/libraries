#!/usr/bin/env python3
"""
Test de integración: Odoo -> Base de datos
Este test verifica la integración completa desde Odoo hasta la base de datos.
"""
import sys
import os
from datetime import datetime

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

def test_odoo_to_database_integration():
    """
    Test principal que lee productos de Odoo y los inserta en la base de datos.
    """
    print("🧪 TESTING ODOO -> DATABASE INTEGRATION")
    print("=" * 60)
    
    # Paso 1: Limpiar la base de datos
    print("\n🗑️ Limpiando base de datos...")
    if not clean_database():
        print("❌ Error limpiando la base de datos")
        return False
    
    # Paso 2: Leer productos de Odoo
    print("\n📖 Leyendo productos de Odoo...")
    products_data = fetch_products_from_odoo()
    if not products_data:
        print("❌ Error leyendo productos de Odoo")
        return False
    
    # Paso 3: Insertar productos en la base de datos
    print("\n💾 Insertando productos en la base de datos...")
    if not insert_products_to_database(products_data):
        print("❌ Error insertando productos en la base de datos")
        return False
    
    # Paso 4: Verificar inserción
    print("\n✅ Verificando inserción...")
    if not verify_database_insertion(products_data):
        print("❌ Error en la verificación")
        return False
    
    print("\n🎉 ¡Integración Odoo -> Base de datos completada exitosamente!")
    return True


def clean_database():
    """Limpiar la tabla de productos para el test."""
    try:
        from common.database import database
        
        with database.get_cursor() as cursor:
            cursor.execute("DELETE FROM products;")
            cursor.execute("SELECT COUNT(*) as count FROM products;")
            count = cursor.fetchone()['count']
            print(f"✅ Base de datos limpiada. Productos restantes: {count}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error limpiando base de datos: {e}")
        return False


def fetch_products_from_odoo():
    """Leer 10 productos de Odoo."""
    try:
        from odoo_api.product import OdooProduct
        from common.config import config
        
        # Configuración de Odoo
        odoo_config = config.get_odoo_config(use_test=False)
        print(f"🔗 Conectando a Odoo: {odoo_config.get('url')}")
        
        odoo = OdooProduct(**odoo_config)
        
        # Obtener productos activos
        active_skus = odoo.get_active_skus()
        print(f"📊 SKUs activos disponibles: {len(active_skus)}")
        
        # Tomar solo los primeros 10
        selected_skus = list(active_skus)[:10]
        print(f"📋 SKUs seleccionados: {selected_skus}")
        
        # Crear un dominio para filtrar solo los SKUs seleccionados
        domain = [
            ('default_code', 'in', selected_skus),
            ('active', '=', True)
        ]
        
        # Obtener datos completos de los productos
        try:
            products_df = odoo.read_products_for_embeddings(domain)
            products_data = products_df.to_dict('records')
            print(f"✅ Productos obtenidos exitosamente: {len(products_data)}")
        except Exception as e:
            print(f"❌ Error obteniendo productos: {e}")
            return []
        
        print(f"📦 Total de productos obtenidos: {len(products_data)}")
        
        # Mostrar información de los productos
        if products_data:
            print("\n📋 Productos obtenidos:")
            for i, product in enumerate(products_data[:5], 1):  # Mostrar solo los primeros 5
                print(f"  {i}. {product.get('default_code', 'N/A')} - {product.get('name', 'N/A')[:50]}...")
        
        return products_data
        
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return []


def insert_products_to_database(products_data):
    """Insertar productos en la base de datos usando db_manager."""
    try:
        import pandas as pd
        from db_manager.product_updater import ProductUpdater
        
        print(f"📊 Preparando {len(products_data)} productos para inserción...")
        
        # Convertir a DataFrame
        df = pd.DataFrame(products_data)
        
        # Mapear campos de Odoo a campos de la base de datos
        if 'default_code' in df.columns:
            df['sku'] = df['default_code']
        
        # Mapear otros campos necesarios
        field_mapping = {
            'categ_id_id': 'category_id',
            'categ_id_name': 'category_name',
            'write_date': 'last_update',
            'uom_id_id': 'uom_id',
            'uom_id_name': 'uom_name',
            'uom_po_id_id': 'uom_po_id',
            'company_id_id': 'company_id',
            'product_tmpl_id_id': 'product_tmpl_id',
            'active': 'is_active'
        }
        
        for odoo_field, db_field in field_mapping.items():
            if odoo_field in df.columns:
                df[db_field] = df[odoo_field]
        
        # Eliminar campos Many2one originales que pueden causar problemas
        fields_to_remove = ['categ_id', 'uom_id', 'uom_po_id', 'company_id', 'product_tmpl_id', 'product_tag_ids', 'product_tag_ids_list']
        for field in fields_to_remove:
            if field in df.columns:
                df = df.drop(columns=[field])
        
        # Asegurar que campos requeridos existen con valores por defecto
        required_fields = {
            'is_active': True,
            'list_price': 0.0,
            'standard_price': 0.0,
            'weight': 0.0,
            'volume': 0.0,
            'sale_ok': True,
            'purchase_ok': True
        }
        
        for field, default_value in required_fields.items():
            if field not in df.columns:
                df[field] = default_value
        
        # Mostrar información del DataFrame
        print(f"📋 Columnas disponibles: {list(df.columns)}")
        print(f"📦 Productos a insertar: {len(df)}")
        
        # Crear el updater
        updater = ProductUpdater()
        
        # Insertar productos
        print("💾 Ejecutando inserción...")
        affected_skus = updater.upsert_products(df)
        
        print(f"✅ Productos insertados/actualizados: {len(affected_skus)}")
        print(f"📋 SKUs afectados: {affected_skus}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error insertando productos: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_database_insertion(products_data):
    """Verificar que los productos se insertaron correctamente."""
    try:
        from common.database import database
        
        # Verificar conteo total
        with database.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM products;")
            total_count = cursor.fetchone()['count']
            print(f"📊 Total de productos en BD: {total_count}")
            
            # Verificar productos específicos
            expected_skus = [p.get('default_code') for p in products_data if p.get('default_code')]
            print(f"🔍 Verificando {len(expected_skus)} SKUs específicos...")
            
            found_skus = []
            for sku in expected_skus:
                cursor.execute("SELECT sku FROM products WHERE sku = %s;", (sku,))
                result = cursor.fetchone()
                if result:
                    found_skus.append(result['sku'])
                    print(f"✅ SKU encontrado: {sku}")
                else:
                    print(f"❌ SKU no encontrado: {sku}")
            
            print(f"📋 SKUs encontrados: {len(found_skus)}/{len(expected_skus)}")
            
            # Verificar algunos campos específicos
            if found_skus:
                sample_sku = found_skus[0]
                cursor.execute("""
                    SELECT sku, name, description, is_active, list_price, text_for_embedding
                    FROM products WHERE sku = %s;
                """, (sample_sku,))
                sample_product = cursor.fetchone()
                
                print(f"\n🔍 Producto de muestra ({sample_sku}):")
                print(f"  Nombre: {sample_product['name']}")
                print(f"  Descripción: {sample_product['description'][:100] if sample_product['description'] else 'N/A'}...")
                print(f"  Activo: {sample_product['is_active']}")
                print(f"  Precio: {sample_product['list_price']}")
                print(f"  Texto para embedding: {'Sí' if sample_product['text_for_embedding'] else 'No'}")
        
        return len(found_skus) > 0
        
    except Exception as e:
        print(f"❌ Error verificando inserción: {e}")
        return False


def main():
    """Función principal del test."""
    print("🚀 INICIANDO TEST DE INTEGRACIÓN ODOO -> DATABASE")
    print("=" * 60)
    
    success = test_odoo_to_database_integration()
    
    if success:
        print("\n🎯 TEST COMPLETADO EXITOSAMENTE")
        print("📋 Resumen:")
        print("  - Productos leídos desde Odoo")
        print("  - Productos insertados en la base de datos")
        print("  - Verificación de inserción completada")
        print("\n✅ La integración Odoo -> Database está funcionando correctamente")
        return 0
    else:
        print("\n❌ TEST FALLÓ")
        print("💡 Revisa los errores anteriores para identificar el problema")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 