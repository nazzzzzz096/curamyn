from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user
from app.chat_service.services.chat_summary_service import save_summary
from app.chat_service.schemas.chat_summary_schema import ChatSummaryRequest

router = APIRouter(
    prefix="/chat",
    tags=["chat-summary"],
)


@router.post(
    "/summary",
    status_code=status.HTTP_201_CREATED,
)
def save_chat_summary(
    payload: ChatSummaryRequest,
    user=Depends(get_current_user),
):
    """
    Save a persistent summary of a chat session.
    """
    save_summary(
        user_id=user.id,
        summary=payload.summary,
    )

    return {"status": "saved"}
