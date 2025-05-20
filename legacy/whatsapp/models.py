from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class WhatsAppTextMessage(BaseModel):
    """Data model for WhatsApp text message payload"""
    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str
    type: Literal["text"] = "text"
    text: Dict[str, Any] = Field(..., example={"preview_url": False, "body": "Hello World"})

class WhatsAppImageMessage(BaseModel):
    """Data model for WhatsApp image message payload"""
    messaging_product: str = "whatsapp"
    to: str
    type: Literal["image"] = "image"
    image: Dict[str, Any]

class WhatsAppMediaResponse(BaseModel):
    """Response from media upload"""
    id: str
    messaging_product: str

class WhatsAppMessageResponse(BaseModel):
    """Response from sending a message"""
    messaging_product: str
    contacts: List[Dict[str, Any]]
    messages: List[Dict[str, Any]] 