"""
Utilidades para manejo de inventario desde Odoo

Este módulo contiene funciones para obtener información de inventario
desde Odoo de manera eficiente y robusta.
"""

import sys
from pathlib import Path
from typing import Dict, List

try:
    from config_manager import secrets
except ImportError:
    print("Warning: config_manager not available")
    secrets = None


def get_inventory_from_odoo(skus: List[str], use_test_odoo: bool = False) -> Dict[str, Dict]:
    """
    Obtener inventario desde Odoo para una lista de SKUs.
    
    Args:
        skus: Lista de SKUs a consultar
        use_test_odoo: Si usar entorno de test
        
    Returns:
        Dict con SKU -> info de inventario con estructura:
        {
            'sku': {
                'found': bool,
                'qty_available': float,
                'product_name': str
            }
        }
    """
    try:
        # Importar aquí para evitar dependencias circulares
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "odoo-api" / "src"))
        from odoo_api.warehouses import OdooWarehouse
        
        if not secrets:
            raise Exception("Configuración de secrets no disponible")
        
        # Obtener configuración de Odoo
        odoo_config = secrets.get_odoo_config(use_test=use_test_odoo)
        odoo_warehouse = OdooWarehouse(
            db=odoo_config['db'],
            url=odoo_config['url'],
            username=odoo_config['username'],
            password=odoo_config['password']
        )
        
        # Normalizar SKUs a string para alinear con Odoo (evita miss-match int vs str)
        skus_str = [str(s) for s in skus]

        # Obtener inventario para todos los SKUs (usar batch para eficiencia)
        inventory_data = {}
        batch_size = 50  # Procesar en lotes para evitar timeouts
        
        for i in range(0, len(skus_str), batch_size):
            batch_skus = skus_str[i:i+batch_size]
            try:
                batch_inventory = odoo_warehouse.get_stock_by_sku(batch_skus)
                # Asegurar claves string
                inventory_data.update({str(k): v for k, v in batch_inventory.items()})
                print(f"   Procesado lote {i//batch_size + 1}/{(len(skus)-1)//batch_size + 1}")
            except Exception as e:
                print(f"   Error en lote {i//batch_size + 1}: {e}")
                # Continuar con el siguiente lote
                continue
        
        return inventory_data
        
    except Exception as e:
        print(f"Error conectando a Odoo: {e}")
        print("Nota: Se requiere configuración de Odoo en config_manager")
        return {}


def validate_inventory_data(inventory_data: Dict[str, Dict]) -> Dict[str, bool]:
    """
    Validar que los datos de inventario tengan la estructura esperada.
    
    Args:
        inventory_data: Datos de inventario desde Odoo
        
    Returns:
        Dict con SKU -> bool indicando si los datos son válidos
    """
    validation_results = {}
    
    for sku, data in inventory_data.items():
        is_valid = (
            isinstance(data, dict) and
            'found' in data and
            'qty_available' in data and
            isinstance(data.get('found'), bool) and
            isinstance(data.get('qty_available'), (int, float))
        )
        validation_results[sku] = is_valid
    
    return validation_results


def get_inventory_summary(inventory_data: Dict[str, Dict]) -> Dict[str, any]:
    """
    Generar resumen de los datos de inventario obtenidos.
    
    Args:
        inventory_data: Datos de inventario desde Odoo
        
    Returns:
        Dict con estadísticas del inventario
    """
    total_skus = len(inventory_data)
    found_skus = sum(1 for data in inventory_data.values() if data.get('found', False))
    total_stock = sum(
        data.get('qty_available', 0) 
        for data in inventory_data.values() 
        if data.get('found', False)
    )
    
    return {
        'total_skus_requested': total_skus,
        'skus_found_in_odoo': found_skus,
        'skus_not_found': total_skus - found_skus,
        'total_stock_units': total_stock,
        'success_rate': (found_skus / total_skus * 100) if total_skus > 0 else 0
    }
