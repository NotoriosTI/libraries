"""
Product Engine Package

A robust and automated engine for synchronizing product catalogs from Odoo to PostgreSQL
with OpenAI embeddings generation for enhanced search and recommendation capabilities.

This package provides:
- Incremental product synchronization from Odoo
- PostgreSQL integration with pgvector support
- OpenAI embeddings generation for product text data
- Comprehensive error handling and logging
- Production-ready configuration management

Main Components:
- ProductsSyncEngine: Main orchestrator for the sync process
- OdooProduct: Specialized Odoo API client for product extraction
- ProductDBUpdater: Database operations with pgvector support
- OpenAIEmbeddingGenerator: Embedding generation using OpenAI API

Usage:
    from product_engine import ProductsSyncEngine
    
    # Initialize the sync engine
    engine = ProductsSyncEngine(use_test_odoo=False)
    
    # Run synchronization
    results = engine.run_sync()
    
    # Check results
    if results["success"]:
        print(f"Synced {results['products_processed']} products")
"""

__version__ = "0.1.0"
__author__ = "Bastian Ibañez"
__email__ = "bastian.miba@gmail.com"

# Main exports
from .main import ProductsSyncEngine, OdooProduct
from .database_updater import ProductDBUpdater
from .embedding_generator import OpenAIEmbeddingGenerator
from .config import config

__all__ = [
    "ProductsSyncEngine",
    "OdooProduct", 
    "ProductDBUpdater",
    "OpenAIEmbeddingGenerator",
    "config",
    "__version__"
]
