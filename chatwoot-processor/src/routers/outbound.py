from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from src.adapters import get_chatwoot_adapter
from src.adapters.errors import ChatwootAdapterError
from src.db.session import get_async_sessionmaker
from src.models.conversation import Conversation
from src.services.message_dispatcher import dispatch_outbound_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outbound", tags=["chatwoot"])


@router.post("/send")
async def send_outbound(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:  # pragma: no cover - handled by FastAPI validation
        logger.warning("Invalid JSON payload for outbound send: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload_must_be_object")

    conversation_id = _coerce_conversation_id(payload)
    content = _coerce_content(payload)

    adapter_env = "production" if payload.get("live") else "local"
    adapter = get_chatwoot_adapter(env=adapter_env)

    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found",
            )

        if session.in_transaction():
            await session.commit()

        try:
            response = await dispatch_outbound_message(session, adapter, conversation, content)
        except ChatwootAdapterError as exc:
            logger.warning(
                "Adapter failure conversation_id=%s: %s", conversation_id, exc, exc_info=True
            )
            detail = {
                "conversation_id": conversation_id,
                "status": "failed",
                "error": str(exc),
                "payload": exc.payload,
            }
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
        except ValueError as exc:
            logger.warning(
                "Outbound validation error conversation_id=%s: %s", conversation_id, exc
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected outbound failure conversation_id=%s", conversation_id)
            detail = {
                "conversation_id": conversation_id,
                "status": "failed",
                "error": str(exc),
            }
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail) from exc

    return {"conversation_id": conversation_id, "response": response}


def _coerce_conversation_id(payload: dict[str, Any]) -> int:
    if "conversation_id" not in payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="conversation_id_required")

    raw_value = payload["conversation_id"]
    try:
        conversation_id = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_conversation_id") from exc

    if conversation_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_conversation_id")

    return conversation_id


def _coerce_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="content_required")
    return content
