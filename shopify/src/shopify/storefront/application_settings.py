# configuration/application_settings.py
"""Application configuration settings."""

from pydantic_settings import BaseSettings
from typing import Optional


class ApplicationSettings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Keys
    OPENAI_API_KEY: str
    WHATSAPP_API_KEY: Optional[str] = None

    # Shopify Configuration - Alineado con los errores de Pydantic
    SHOPIFY_API_KEY: Optional[str] = None # Mantenemos este por si se usa en otro lado o como alias futuro
    SHOPIFY_API_SECRET: Optional[str] = None # Campo reportado en el error
    SHOPIFY_TOKEN_API_ADMIN: Optional[str] = None     # Campo reportado en el error
    SHOPIFY_SHOP_URL: Optional[str] = None     # Renombrado desde SHOPIFY_STORE_URL y campo reportado
    SHOPIFY_API_VERSION: Optional[str] = None  # Campo reportado en el error
    SHOPIFY_TOKEN_API_STOREFRONT: Optional[str] = None

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # LangGraph Configuration
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = "REEMPLAZA_ESTO_CON_TU_CLAVE_DE_LANGSMITH_REAL" # ¡EDITA ESTE VALOR!
    LANGCHAIN_PROJECT: str = "emilia"  # Usando el proyecto que ya está funcionando
    
    # Model Configuration
    LARGE_MODEL: str = "gpt-4.1-mini"
    MEDIUM_MODEL: str = "gpt-4.1-mini"
    SMALL_MODEL: str = "gpt-4.1-mini"
    LLM_MODEL: str = "gpt-4.1-mini"
    LLM_TEMPERATURE: float = 0.3
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Application Settings
    APP_TIMEZONE: str = "UTC" # Default timezone for the application
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


# Create settings instance
settings = ApplicationSettings()
