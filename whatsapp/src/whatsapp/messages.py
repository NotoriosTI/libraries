import requests
import logging
import json
from typing import Optional, Dict, Any, Union

from src.external_integrations.whatsapp.api_whatsapp import whatsapp_service

logger = logging.getLogger(__name__)

class WhatsAppMessages:
    """Class for handling WhatsApp message operations"""
    
    def __init__(self, service=None):
        self.service = service or whatsapp_service
    
    def send_typing_indicator(self, message_id: str) -> bool:
        """
        Sends a typing indicator and marks a message as read.
        
        Args:
            message_id: WhatsApp message ID received
            
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
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {
                "type": "text"
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            logger.info(f"Typing indicator sent for message ID: {message_id}")
            return True
        except requests.Timeout:
            logger.error(f"Timeout sending typing indicator for message ID: {message_id}")
            return False
        except requests.RequestException as e:
            logger.error(f"Request error sending typing indicator for message ID: {message_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending typing indicator for message ID: {message_id}: {e}")
            return False

    def send_message(self, data: Union[Dict[str, Any], str]) -> Optional[Dict[str, Any]]:
        """
        Sends a message through the WhatsApp API.
        
        Args:
            data: Message payload as dict or JSON string
            
        Returns:
            Optional[Dict[str, Any]]: API response or None if failed
        """
        url = f"{self.service.api_url}/{self.service.api_version}/{self.service.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.service.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            if isinstance(data, str):
                response = requests.post(url, data=data, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=10)
                
            logger.info(f'RESPONSE: {response.content}')
            logger.info(f'RESPONSE SC: {response.status_code}')
            response.raise_for_status()
            self.service._log_http_response(response)
            return response.json()
        except requests.Timeout:
            logger.error("Timeout occurred while sending message")
            return None
        except requests.RequestException as e:
            logger.error(f"Request failed due to: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return None

    def send_text_message(self, phone_number: str, message: str) -> bool:
        """
        Sends a text message to a WhatsApp number.
        
        Args:
            phone_number: Recipient's phone number
            message: Text message to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }
        
        response = self.send_message(payload)
        return response is not None

# Shared instance
whatsapp_messages = WhatsAppMessages() 