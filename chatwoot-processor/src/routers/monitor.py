from fastapi import APIRouter, Depends, HTTPException

from src.adapters.base_db_adapter import BaseDBAdapter
from src.dependencies import get_db_adapter
from src.models.message import Message

router = APIRouter(tags=["messages"])


@router.get("/messages/count")
async def message_count(db: BaseDBAdapter = Depends(get_db_adapter)) -> dict:
    messages = await db.list_messages()
    return {"count": len(messages)}


@router.get("/messages/latest", response_model=Message)
async def latest_message(db: BaseDBAdapter = Depends(get_db_adapter)) -> Message:
    messages = await db.list_messages()
    if not messages:
        raise HTTPException(status_code=404, detail="No messages available")
    return messages[-1]
