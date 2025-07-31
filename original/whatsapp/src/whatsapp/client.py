import logging
from typing import Optional, Dict, Any, Union

from .api_whatsapp import whatsapp_service
from .messages import WhatsAppMessages
from .media import WhatsAppMedia

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """Unified client for WhatsApp API integrating messages and media functionality"""
    
    def __init__(self, service=None):
        self.service = service or whatsapp_service
        self.messages = WhatsAppMessages(self.service)
        self.media = WhatsAppMedia(self.service)
    
    # Message methods
    def send_text_message(self, phone_number: str, message: str) -> bool:
        """Send a text message to a WhatsApp number"""
        return self.messages.send_text_message(phone_number, message)
    
    def send_typing_indicator(self, message_id: str) -> bool:
        """Send typing indicator and mark message as read"""
        return self.messages.send_typing_indicator(message_id)
    
    def send_message(self, data: Union[Dict[str, Any], str]) -> Optional[Dict[str, Any]]:
        """Send a raw message payload to WhatsApp API"""
        return self.messages.send_message(data)
    
    # Media methods
    def read_media_url(self, media_id: str) -> Optional[str]:
        """Get temporary URL for a media ID"""
        return self.media.read_media_url(media_id)
    
    def read_n_download_media(self, media_url: str) -> Optional[bytes]:
        """Download media content from URL"""
        return self.media.read_n_download_media(media_url)
    
    def upload_media(self, file_path: str) -> Optional[str]:
        """Upload a file to WhatsApp and get media ID"""
        return self.media.upload_media(file_path)
    
    def send_image_message(
        self, 
        phone_number: str, 
        media_id: str, 
        caption: Optional[str] = None
    ) -> bool:
        """Send an image message using media ID"""
        return self.media.send_image_message(phone_number, media_id, caption)

# Shared instance
whatsapp_client = WhatsAppClient() 