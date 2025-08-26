"""
Shopify Library - Librería Python para interactuar con las APIs de Shopify

Este paquete proporciona interfaces para:
- Shopify Admin API (GraphQL)
- Shopify Storefront API (GraphQL)
"""

# Admin API (GraphQL)
from .graphql import ShopifyAPI, ShopifyOrders, ShopifyProducts

# Storefront API (GraphQL) 
from .storefront import StorefrontAPI, StorefrontSearch

__version__ = "1.0.2"

__all__ = [
    # Admin API
    'ShopifyAPI',
    'ShopifyOrders', 
    'ShopifyProducts',
    # Storefront API
    'StorefrontAPI',
    'StorefrontSearch'
]
