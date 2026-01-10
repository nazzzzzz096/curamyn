from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.chat_service.repositories.session_repositories import delete_chat_session
from app.chat_service.repositories.session_repositories import (
    get_user_sessions_by_session_id,
)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.get("/history")
def get_chat_history(
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Return full chat history for a session.
    """
    messages = get_user_sessions_by_session_id(
        user_id=current_user["sub"],
        session_id=session_id,
    )

    return {
        "messages": messages or []
    }

@router.delete("/end-session")
def end_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    delete_chat_session(
        user_id=current_user["sub"],
        session_id=session_id,
    )
    return {"status": "session deleted"}