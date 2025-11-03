from fastapi import APIRouter, Depends

from src.adapters.mock_db_adapter import MockDBAdapter
from src.dependencies import get_db_adapter
from src.models.message import Message

router = APIRouter(tags=["messages"])


@router.post("/webhook/chatwoot")
async def receive_inbound(
    msg: Message, db: MockDBAdapter = Depends(get_db_adapter)
) -> dict:
    """
    Persist inbound or outbound messages received from Chatwoot webhooks.
    """

    if msg.direction == "outbound":
        msg.status = "queued"
    else:
        msg.direction = "inbound"
        msg.status = "received"

    await db.persist_message(msg)
    return {"status": "ok", "msg_id": msg.id, "direction": msg.direction}
