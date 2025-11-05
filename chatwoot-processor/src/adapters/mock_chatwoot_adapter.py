import asyncio
from random import random

from src.interfaces.protocols import MessageDeliveryClient
from src.models.message import Message


class MockChatwootAdapter(MessageDeliveryClient):
    """
    Mock Chatwoot client that simulates network delivery.
    """

    failure_rate: float

    def __init__(self, failure_rate: float = 0.2) -> None:
        self.failure_rate = failure_rate

    async def send_message(self, msg: Message) -> bool:
        print(f"[Chatwoot] Sending message {msg.id}: '{msg.content}'")
        await asyncio.sleep(0.3)
        delivered = random() > self.failure_rate
        print(f"[Chatwoot] {'Sent' if delivered else 'Failed'} message {msg.id}")
        return delivered
