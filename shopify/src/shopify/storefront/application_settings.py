# configuration/application_settings.py
"""Application configuration settings for Shopify Storefront API."""

from pydantic_settings import BaseSettings
from typing import Optional


class StorefrontSettings(BaseSettings):
    """Storefront-specific settings with environment variable support."""
    
    # Shopify Configuration - Solo las variables que realmente se usan
    SHOPIFY_SHOP_URL: Optional[str] = None
    SHOPIFY_API_VERSION: Optional[str] = "2025-01"
    SHOPIFY_TOKEN_API_STOREFRONT: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Configuración para permitir variables extra en .env sin errores
        extra = "ignore"  # Ignora variables extra en lugar de fallar
        case_sensitive = False  # Permite variaciones de mayúsculas/minúsculas


# Create settings instance
settings = StorefrontSettings()
