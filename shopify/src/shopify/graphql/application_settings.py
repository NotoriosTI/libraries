# configuration/application_settings.py
"""Application configuration settings for Shopify GraphQL API."""

from pydantic_settings import BaseSettings
from typing import Optional


class GraphQLSettings(BaseSettings):
    """GraphQL-specific settings with environment variable support."""
    
    # Shopify Configuration - Solo las variables que realmente se usan en GraphQL
    SHOPIFY_SHOP_URL: Optional[str] = None
    SHOPIFY_API_VERSION: Optional[str] = "2025-01"
    SHOPIFY_TOKEN_API_ADMIN: Optional[str] = None
    
    # Variables no utilizadas en GraphQL (descartadas):
    # SHOPIFY_API_KEY - No se usa en la implementación GraphQL actual
    # SHOPIFY_API_SECRET - No se usa en la implementación GraphQL actual  
    # SINCE_ID - No se usa en la implementación GraphQL actual
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Configuración para permitir variables extra en .env sin errores
        extra = "ignore"  # Ignora variables extra en lugar de fallar
        case_sensitive = False  # Permite variaciones de mayúsculas/minúsculas


# Create settings instance
settings = GraphQLSettings()
