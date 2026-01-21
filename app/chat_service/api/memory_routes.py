from fastapi import APIRouter, Depends, status, Request

from app.core.dependencies import get_current_user
from app.chat_service.repositories.session_repositories import (
    delete_user_sessions,
    delete_chat_sessions_by_user,
)
from app.consent_service.service import create_or_update_consent
from app.core.rate_limit import limiter

router = APIRouter(
    prefix="/memory",
    tags=["Memory"],
)


@router.delete(
    "/clear",
    status_code=status.HTTP_200_OK,
)
def clear_memory(
    current_user: dict = Depends(get_current_user),
):
    """
    Delete all stored memory for the current user.
    """
    deleted_sessions = delete_chat_sessions_by_user(current_user["sub"])
    deleted_count = delete_user_sessions(current_user["sub"])

    return {
        "message": "Memory cleared successfully.",
        "deleted_sessions": deleted_count,
        "deleted_chat_session": deleted_sessions,
    }


@router.delete(
    "/clear-and-disable",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("1/minute")
def clear_and_disable_memory(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete memory and disable future memory storage.
    """
    deleted_count = delete_user_sessions(current_user["sub"])
    deleted_sessions = delete_chat_sessions_by_user(current_user["sub"])
    create_or_update_consent(
        current_user["sub"],
        {"memory": False},
    )

    return {
        "message": "Memory cleared and future storage disabled.",
        "deleted_sessions": deleted_count,
        "deleted_chat_session": deleted_sessions,
    }
