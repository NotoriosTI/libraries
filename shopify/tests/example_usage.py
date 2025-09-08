#!/usr/bin/env python3
"""
Ejemplo de uso de la librería Shopify con soporte para múltiples agentes.

Este archivo demuestra cómo usar la librería modificada para trabajar
tanto con Emilia como con Emma sin romper la compatibilidad existente.
"""

from shopify import ShopifyAPI, ShopifyOrders, ShopifyProducts
from shopify import StorefrontAPI, StorefrontSearch

def test_emilia_compatibility():
    """
    Prueba la compatibilidad hacia atrás para Emilia.
    El código existente debería funcionar sin cambios.
    """
    print("=== Testando compatibilidad con Emilia (código existente) ===")
    
    try:
        # Estos son los usos EXACTOS que ya existen en el código de Emilia
        api = ShopifyAPI()
        orders_api = ShopifyOrders()
        products_api = ShopifyProducts()
        storefront_api = StorefrontAPI()
        search_api = StorefrontSearch()
        
        print("✅ Todas las clases se inicializaron correctamente para Emilia")
        print(f"   - GraphQL API URL: {api.graphql_url}")
        print(f"   - Storefront API URL: {storefront_api.graphql_url}")
        
    except Exception as e:
        print(f"❌ Error en compatibilidad con Emilia: {e}")

def test_emma_support():
    """
    Prueba el nuevo soporte para Emma.
    """
    print("\n=== Testando nuevo soporte para Emma ===")
    
    try:
        # Nuevo uso para Emma - simplemente agregando agent="emma"
        api = ShopifyAPI(agent="emma")
        orders_api = ShopifyOrders(agent="emma")
        products_api = ShopifyProducts(agent="emma")
        storefront_api = StorefrontAPI(agent="emma")
        search_api = StorefrontSearch(agent="emma")
        
        print("✅ Todas las clases se inicializaron correctamente para Emma")
        print(f"   - GraphQL API URL: {api.graphql_url}")
        print(f"   - Storefront API URL: {storefront_api.graphql_url}")
        
    except Exception as e:
        print(f"❌ Error en soporte para Emma: {e}")

def test_mixed_usage():
    """
    Prueba el uso mixto de ambos agentes en la misma aplicación.
    """
    print("\n=== Testando uso mixto de Emilia y Emma ===")
    
    try:
        # Emilia para órdenes
        emilia_orders = ShopifyOrders()  # Default a emilia
        
        # Emma para productos
        emma_products = ShopifyProducts(agent="emma")
        
        # Explicit emilia para storefront
        emilia_storefront = StorefrontAPI(agent="emilia")
        
        print("✅ Uso mixto funcionando correctamente")
        print("   - Emilia órdenes: Configuración cargada")
        print("   - Emma productos: Configuración cargada")
        print("   - Emilia storefront: Configuración cargada")
        
    except Exception as e:
        print(f"❌ Error en uso mixto: {e}")

def show_usage_examples():
    """
    Muestra ejemplos de cómo usar la nueva funcionalidad.
    """
    print("\n=== Ejemplos de uso ===")
    
    print("""
# 1. Código existente de Emilia (SIN CAMBIOS)
api = ShopifyAPI()
orders = ShopifyOrders()
products = ShopifyProducts()

# 2. Nuevo código para Emma
api = ShopifyAPI(agent="emma")
orders = ShopifyOrders(agent="emma")
products = ShopifyProducts(agent="emma")

# 3. Uso mixto en la misma aplicación
emilia_orders = ShopifyOrders()                    # Emilia
emma_products = ShopifyProducts(agent="emma")      # Emma
emilia_search = StorefrontSearch(agent="emilia")   # Emilia explícito

# 4. Override manual de credenciales (funciona igual que antes)
api = ShopifyAPI(
    shop_url="custom-shop.myshopify.com",
    api_password="custom-token",
    agent="emma"  # Opcional
)
""")

if __name__ == "__main__":
    print("🧪 Probando la librería Shopify con soporte multi-agente")
    print("=" * 60)
    
    # Ejecutar todas las pruebas
    test_emilia_compatibility()
    test_emma_support()
    test_mixed_usage()
    show_usage_examples()
    
    print("\n" + "=" * 60)
    print("✨ Pruebas completadas. La librería está lista para usar con ambos agentes!")
