"""
DB Manager Module

Módulo responsable de las operaciones de actualización y sincronización de la base de datos.
Incluye sincronización desde Odoo, generación de embeddings y operaciones de escritura.
"""

from db_manager.sync_manager import SyncManager
from db_manager.product_updater import ProductUpdater

__all__ = [
    "SyncManager",
    "ProductUpdater"
] 