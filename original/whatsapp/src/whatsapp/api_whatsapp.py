import requests
import logging
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class WhatsAppSettings(BaseSettings):
    WHATSAPP_API_URL: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_API_VERSION: str
    WHATSAPP_PHONE_NUMBER_ID: str
    
    class Config:
        env_file = ".env"

class WhatsAppService:
    """Service for interacting with WhatsApp Business API"""
    
    def __init__(self):
        settings = WhatsAppSettings()
        self.api_url = settings.WHATSAPP_API_URL
        self.api_key = settings.WHATSAPP_ACCESS_TOKEN
        self.api_version = settings.WHATSAPP_API_VERSION
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        
        if not all([self.api_url, self.api_key, self.api_version, self.phone_number_id]):
            logger.warning("WhatsApp API not configured correctly. Verify environment variables.")

    def _log_http_response(self, response):
        """Log HTTP response for debugging."""
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Content-type: {response.headers.get('content-type')}")
        logger.info(f"Body: {response.text}")

# Shared instance
whatsapp_service = WhatsAppService() 