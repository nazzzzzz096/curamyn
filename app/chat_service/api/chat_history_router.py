from fastapi import APIRouter, Depends, Query
from typing import Dict, List,Any

from app.core.dependencies import get_current_user
from app.chat_service.repositories.session_repositories import (
    delete_chat_session,
    get_user_sessions_by_session_id,
)
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)



def _serialize_message(db_message: dict) -> Dict[str, object]:
    msg_type = db_message.get("type", "text")

    if msg_type == "audio":
        return {
            "author": db_message.get("author"),
            "type": "audio",
            "audio_data": db_message.get("audio_data"),
            "mime_type": db_message.get("mime_type"),
            "sent": db_message.get("sent", False),
            "timestamp": db_message.get("created_at"),
        }

    if msg_type == "image":
        return {
            "author": db_message.get("author"),
            "type": "image",
            "image_data": db_message.get("image_data"),
            "mime_type": db_message.get("mime_type"),
            "sent": db_message.get("sent", False),
            "timestamp": db_message.get("created_at"),
        }

    return {
        "author": db_message.get("author"),
        "type": "text",
        "text": db_message.get("text", ""),
        "sent": db_message.get("sent", False),
        "timestamp": db_message.get("created_at"),
    }



@router.get("/history")
def get_chat_history(
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, List[Dict[str, object]]]:
    """
    Return normalized chat history for a session.

    Args:
        session_id: Chat session identifier.
        current_user: Authenticated user.

    Returns:
        dict: List of normalized chat messages.
    """
    user_id = current_user.get("sub")

    logger.info(
        "Chat history endpoint HIT",
        extra={
            "session_id": session_id,
            "user_id": user_id,
        },
    )

    raw_messages = get_user_sessions_by_session_id(
        user_id=user_id,
        session_id=session_id,
    ) or []

    messages = [_serialize_message(msg) for msg in raw_messages]

    logger.info(
        "Chat history serialized",
        extra={
            "count": len(messages),
            "session_id": session_id,
        },
    )
    

    return {"messages": messages}


@router.delete("/end-session")
def end_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a chat session for the current user.
    """
    delete_chat_session(
        user_id=current_user["sub"],
        session_id=session_id,
    )

    logger.info(
        "Chat session deleted",
        extra={
            "session_id": session_id,
            "user_id": current_user.get("sub"),
        },
    )

    return {"status": "session deleted"}
