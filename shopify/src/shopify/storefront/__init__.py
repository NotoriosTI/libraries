"""
Shopify Storefront API Module

Este módulo proporciona funcionalidades para interactuar con la API de Storefront de Shopify.
"""

from .api_shopify_storefront import StorefrontAPI
from .search import StorefrontSearch

__all__ = [
    'StorefrontAPI',
    'StorefrontSearch'
]
