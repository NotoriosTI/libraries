#!/usr/bin/env python3
"""
Script de prueba para verificar la configuración de Product Engine
"""
import sys
import os

# Añadir el directorio src al path (desde tests/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

def test_database_connection():
    """Probar conexión a la base de datos."""
    print("🔗 Probando conexión a base de datos...")
    
    try:
        from product_engine.database_updater import ProductDBUpdater
        
        updater = ProductDBUpdater()
        with updater.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                print(f"✅ Conexión exitosa a PostgreSQL: {version}")
                
                # Verificar extensión pgvector
                cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
                if cursor.fetchone():
                    print("✅ Extensión pgvector instalada")
                else:
                    print("❌ Extensión pgvector NO encontrada")
                
                # Verificar tabla products
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'products'
                    );
                """)
                if cursor.fetchone()[0]:
                    print("✅ Tabla products existe")
                    
                    # Contar productos existentes
                    cursor.execute("SELECT COUNT(*) FROM products;")
                    count = cursor.fetchone()[0]
                    print(f"   📊 Productos en la tabla: {count}")
                else:
                    print("❌ Tabla products NO existe")
                    
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_odoo_connection():
    """Probar conexión a Odoo."""
    print("\n🔗 Probando conexión a Odoo...")
    
    try:
        from odoo_api.product import OdooProduct
        from product_engine.config import config
        
        odoo_config = config.get_odoo_config(use_test=False)
        print(f"   🔗 Conectando a: {odoo_config.get('url', 'URL no configurada')}")
        
        odoo = OdooProduct(**odoo_config)
        
        # Intentar obtener algunos SKUs activos
        active_skus = odoo.get_active_skus()
        print(f"✅ Conexión exitosa a Odoo. SKUs activos encontrados: {len(active_skus)}")
        if active_skus:
            print(f"   📝 Primeros 5 SKUs: {list(active_skus)[:5]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión a Odoo: {e}")
        return False

def test_openai_connection():
    """Probar conexión a OpenAI."""
    print("\n🔗 Probando conexión a OpenAI...")
    
    try:
        from product_engine.embedding_generator import OpenAIEmbeddingGenerator
        
        generator = OpenAIEmbeddingGenerator()
        
        # Generar embedding de prueba
        test_text = "aceite de coco orgánico"
        print(f"   📝 Texto de prueba: '{test_text}'")
        
        embeddings = generator.generate([test_text])
        
        if embeddings and len(embeddings) == 1 and len(embeddings[0]) == 1536:
            print(f"✅ Conexión exitosa a OpenAI. Embedding generado: {len(embeddings[0])} dimensiones")
            print(f"   📊 Primeros 3 valores: {embeddings[0][:3]}")
            return True
        else:
            print("❌ Error: Embedding no válido")
            return False
            
    except Exception as e:
        print(f"❌ Error de conexión a OpenAI: {e}")
        return False

def test_configuration():
    """Probar configuración básica."""
    print("\n⚙️ Probando configuración...")
    
    try:
        from product_engine.config import config
        
        print(f"✅ Entorno: {config.environment}")
        print(f"✅ Es producción: {config.is_production}")
        print(f"✅ Es desarrollo: {config.is_development}")
        
        # Probar configuraciones
        db_config = config.get_database_config()
        print(f"✅ Configuración DB: Host={db_config.get('host')}, DB={db_config.get('database')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error de configuración: {e}")
        return False

def main():
    """Función principal."""
    print("🧪 PROBANDO CONFIGURACIÓN DE PRODUCT ENGINE")
    print("=" * 60)
    
    # Probar cada componente
    config_ok = test_configuration()
    db_ok = test_database_connection()
    odoo_ok = test_odoo_connection()
    openai_ok = test_openai_connection()
    
    print("\n" + "=" * 60)
    print("📋 RESUMEN DE PRUEBAS:")
    print(f"   Configuración: {'✅' if config_ok else '❌'}")
    print(f"   Base de datos: {'✅' if db_ok else '❌'}")
    print(f"   Odoo API:      {'✅' if odoo_ok else '❌'}")
    print(f"   OpenAI API:    {'✅' if openai_ok else '❌'}")
    
    if all([config_ok, db_ok, odoo_ok, openai_ok]):
        print("\n🎉 ¡Todas las pruebas pasaron! Configuración lista.")
        print("\n🚀 Siguiente paso: Ejecutar sincronización con:")
        print("   python -m product_engine.main")
        return 0
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa la configuración.")
        
        if not config_ok:
            print("   💡 Verifica el archivo .env")
        if not db_ok:
            print("   💡 Verifica conexión a PostgreSQL y proxy Cloud SQL")
        if not odoo_ok:
            print("   💡 Verifica credenciales y URL de Odoo")
        if not openai_ok:
            print("   💡 Verifica API key de OpenAI")
            
        return 1

if __name__ == "__main__":
    sys.exit(main()) 