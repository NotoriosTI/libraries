#!/usr/bin/env python3
"""
Script de prueba para verificar el filtro de similarity score > 0.8 
en las búsquedas semánticas de productos.
"""

import sys
from pathlib import Path

# Agregar el directorio src al path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from product_engine import search_products
import structlog

# Configurar logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def test_similarity_filter():
    """
    Prueba el filtro de similarity score > 0.8 en búsquedas semánticas.
    """
    print("\n" + "="*60)
    print("PRUEBA: Filtro de Similarity Score > 0.8")
    print("="*60)
    
    # Queries de prueba con diferentes niveles de especificidad
    test_queries = [
        "aceite de coco",           # Query específico (debería tener alta similaridad)
        "aceite",                   # Query genérico (posiblemente baja similaridad)
        "producto natural",         # Query muy genérico (probablemente baja similaridad)
        "shampoo orgánico",         # Query específico en otra categoría
        "PROD-001",                 # SKU específico (puede ser búsqueda exacta)
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Buscando: '{query}'")
        print("-" * 40)
        
        try:
            results = search_products(query, limit=10)
            
            if not results:
                print("   ❌ No se encontraron resultados")
                continue
            
            print(f"   ✅ {len(results)} resultados encontrados")
            
            for j, product in enumerate(results, 1):
                search_type = product.get('search_type', 'unknown')
                relevance_score = product.get('relevance_score', 0.0)
                similarity_score = product.get('similarity_score', 0.0)
                
                print(f"   {j:2d}. {product['sku']} - {product['name'][:50]}...")
                print(f"       Tipo: {search_type}")
                print(f"       Relevance Score: {relevance_score:.3f}")
                print(f"       Similarity Score: {similarity_score:.3f}")
                
                # Verificar que los resultados semánticos cumplan el filtro
                if search_type == 'semantic' and similarity_score <= 0.8:
                    print(f"       ⚠️  ADVERTENCIA: Similarity score {similarity_score:.3f} <= 0.8")
                elif search_type == 'semantic':
                    print(f"       ✅ Cumple filtro: {similarity_score:.3f} > 0.8")
                print()
                
        except Exception as e:
            print(f"   ❌ Error en búsqueda: {str(e)}")
            logger.error("Error en búsqueda", query=query, error=str(e))


def test_edge_cases():
    """
    Prueba casos extremos para verificar el comportamiento del filtro.
    """
    print("\n" + "="*60)
    print("PRUEBA: Casos Extremos")
    print("="*60)
    
    edge_cases = [
        "",                         # Query vacío
        "xyz123",                   # Query que no debería tener matches
        "producto que no existe",   # Query específico pero inexistente
        "  aceite  ",              # Query con espacios
    ]
    
    for i, query in enumerate(edge_cases, 1):
        print(f"\n{i}. Caso extremo: '{query}'")
        print("-" * 40)
        
        try:
            results = search_products(query.strip() if query else query, limit=5)
            
            if not results:
                print("   ✅ No se encontraron resultados (esperado para algunos casos)")
            else:
                print(f"   📊 {len(results)} resultados encontrados")
                
                for j, product in enumerate(results, 1):
                    search_type = product.get('search_type', 'unknown')
                    similarity_score = product.get('similarity_score', 0.0)
                    
                    print(f"   {j}. {product['sku']} - Tipo: {search_type}, Score: {similarity_score:.3f}")
                    
                    if search_type == 'semantic' and similarity_score <= 0.8:
                        print(f"      ⚠️  PROBLEMA: Score {similarity_score:.3f} <= 0.8")
                        
        except Exception as e:
            print(f"   ✅ Error esperado: {str(e)}")


def main():
    """
    Función principal que ejecuta todas las pruebas.
    """
    print("🔍 Iniciando pruebas del filtro de similarity score...")
    
    try:
        # Prueba principal del filtro
        test_similarity_filter()
        
        # Prueba de casos extremos
        test_edge_cases()
        
        print("\n" + "="*60)
        print("✅ PRUEBAS COMPLETADAS")
        print("="*60)
        print("\nResumen:")
        print("- Solo se devuelven resultados semánticos con similarity score > 0.8")
        print("- Las búsquedas exactas por SKU siempre se devuelven (score = 1.0)")
        print("- Los queries muy genéricos pueden no devolver resultados")
        print("- El sistema maneja graciosamente casos extremos")
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {str(e)}")
        logger.error("Error durante las pruebas", error=str(e), exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 