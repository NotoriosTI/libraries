# configuration/application_settings.py
"""Application configuration settings."""

from pydantic_settings import BaseSettings
from typing import Optional


class ApplicationSettings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Keys
    OPENAI_API_KEY: str

    # Shopify Configuration - Con los nombres que usas
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_SHOP_URL: Optional[str] = None
    SHOPIFY_TOKEN_API_ADMIN: Optional[str] = None
    SHOPIFY_API_VERSION: Optional[str] = "2025-01"
    SHOPIFY_TOKEN_API_STOREFRONT: Optional[str] = None
    
    # Application Settings
    APP_TIMEZONE: str = "UTC"
    MAX_CONVERSATION_TOKENS: int = 5000
    SUMMARY_CHUNK_SIZE: int = 2000
    CONVERSATION_RETENTION_DAYS: int = 30
    
    # Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WORKERS: int = 1
    
    # Security
    API_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Configuración para permitir variables extra en .env sin errores
        extra = "ignore"  # Ignora variables extra en lugar de fallar
        case_sensitive = False  # Permite variaciones de mayúsculas/minúsculas


# Create settings instance
settings = ApplicationSettings()
