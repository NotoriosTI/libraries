import requests
import logging
from typing import Optional

from src.external_integrations.whatsapp.api_whatsapp import whatsapp_service

logger = logging.getLogger(__name__)

class WhatsAppMedia:
    """Class for handling WhatsApp media operations"""
    
    def __init__(self, service=None):
        self.service = service or whatsapp_service
    
    def read_media_url(self, media_id: str) -> Optional[str]:
        """
        Gets the temporary download URL for a received media_id.
        
        Args:
            media_id: WhatsApp media ID
            
        Returns:
            Optional[str]: Media URL or None if failed
        """
        url = f"{self.service.api_url}/{self.service.api_version}/{media_id}"
        headers = {
            "Authorization": f"Bearer {self.service.api_key}"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            media_info = resp.json()
            media_url = media_info.get("url")
            if not media_url:
                logger.error(f"No 'url' found in response for media_id={media_id}: {resp.text}")
                return None
            logger.info(f"URL obtained for media_id={media_id}")
            return media_url
        except requests.Timeout:
            logger.error(f"Timeout getting URL for media_id={media_id}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request error getting URL for media_id={media_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting URL for media_id={media_id}: {e}")
            return None

    def read_n_download_media(self, media_url: str) -> Optional[bytes]:
        """
        Downloads content from a WhatsApp media_url using authentication.
    
        Args:
            media_url: The temporary URL provided by WhatsApp.
    
        Returns:
            The downloaded file bytes or None if there's an error.
        """
        if not media_url:
            logger.error("Attempted to download media with an empty URL.")
            return None
    
        headers = {
            "Authorization": f"Bearer {self.service.api_key}"
        }
        try:
            response = requests.get(media_url, headers=headers, timeout=20)  # Timeout for download
            response.raise_for_status()  # Raises exception for 4xx/5xx codes
            logger.info(f"Media downloaded successfully from {media_url[:50]}...")
            return response.content
        except requests.Timeout:
            logger.error(f"Timeout downloading media from {media_url[:50]}...")
            return None
        except requests.RequestException as e:
            logger.error(f"Request error downloading media from {media_url[:50]}...: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading media: {e}")
            return None

    def upload_media(self, file_path: str) -> Optional[str]:
        """
        Uploads a file (image/video) to WhatsApp and returns the media_id.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            Optional[str]: Media ID or None if failed
        """
        url = f"{self.service.api_url}/{self.service.api_version}/{self.service.phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {self.service.api_key}"
        }
        
        try:
            with open(file_path, "rb") as file:
                files = {"file": file}
                data = {"messaging_product": "whatsapp"}
                
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                resp.raise_for_status()
                media_id = resp.json().get("id")
                
                if not media_id:
                    logger.error(f"No media_id obtained: {resp.text}")
                    return None
                    
                logger.info(f"Media uploaded successfully: media_id={media_id}")
                return media_id
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error uploading media to WhatsApp: {e}")
            return None

    def send_image_message(
        self,
        phone_number: str,
        media_id: str,
        caption: Optional[str] = None
    ) -> bool:
        """
        Sends an 'image' type message referencing a previously uploaded media_id.
        
        Args:
            phone_number: Recipient's phone number
            media_id: WhatsApp media ID
            caption: Optional image caption
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        url = f"{self.service.api_url}/{self.service.api_version}/{self.service.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.service.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "image",
            "image": {"id": media_id}
        }
        if caption:
            payload["image"]["caption"] = caption
    
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"Image sent to {phone_number}: media_id={media_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending image to WhatsApp: {e}")
            return False

# Shared instance
whatsapp_media = WhatsAppMedia() 