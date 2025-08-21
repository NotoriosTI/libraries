import os
import json
import sys
from pathlib import Path

# Añadir el directorio src al path para poder importar módulos del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Ahora importar después de configurar las variables
from shopify.storefront.search import StorefrontSearch

def main():
    try:
        # Inicializar la clase StorefrontSearch
        search = StorefrontSearch()
        print("✅ Instancia de StorefrontSearch creada correctamente")
        
        # Términos de búsqueda
        search_terms = ["vainilla", "dulce", "jabón"]
        
        # Probar search_products (búsqueda detallada)
        print("\n--- BÚSQUEDA DETALLADA DE PRODUCTOS ---")
        products_by_term = search.search_products(search_terms, limit_per_term=2)
        
        for term, products in products_by_term.items():
            print(f"\nTérmino de búsqueda: '{term}'")
            print(f"Productos encontrados: {len(products)}")
            
            if products:
                # Mostrar el primer producto como ejemplo
                print(f"\nEjemplo de producto:")
                product = products[0]
                print(f"  ID: {product['id']}")
                print(f"  Título: {product['title']}")
                print(f"  Tipo: {product['product_type']}")
                print(f"  Estado: {product['status']}")
                print(f"  Variantes: {len(product['variants'])}")
        
        # Probar search_products_consolidated (búsqueda simplificada)
        print("\n--- BÚSQUEDA CONSOLIDADA DE PRODUCTOS ---")
        consolidated_products = search.search_products_consolidated(search_terms, limit_per_term=3)
        
        print(f"Total de productos/variantes consolidados: {len(consolidated_products)}")
        
        if consolidated_products:
            # Mostrar algunos ejemplos
            print("\nEjemplos de productos consolidados:")
            for i, product in enumerate(consolidated_products[:3], 1):
                print(f"\nProducto {i}:")
                print(f"  ID: {product['id']}")
                print(f"  Título: {product['title']}")
                print(f"  Variante ID: {product['variant_id']}")
                print(f"  Variante Título: {product['variant_title']}")
                print(f"  SKU: {product['variant_sku']}")
                print(f"  Precio: {product['variant_price']}")
                print(f"  Inventario: {product['variant_inventory_quantity']}")
                
    except Exception as e:
        print(f"❌ Error al ejecutar el test: {e}")
        print("ℹ️ Variables configuradas:")
        print(f"  - API_SECRET_KEY: {os.getenv('SHOPIFY_API_SECRET', 'No configurada')}")
        print(f"  - SHOPIFY_STORE_URL: {os.getenv('SHOPIFY_SHOP_URL', 'No configurada')}")
        print(f"  - SHOPIFY_ACCESS_TOKEN: {os.getenv('SHOPIFY_TOKEN_API_STOREFRONT', 'No configurada')}")
        print(f"  - SHOPIFY_API_VERSION: {os.getenv('SHOPIFY_API_VERSION', 'No configurada')}")


if __name__ == "__main__":
    main()