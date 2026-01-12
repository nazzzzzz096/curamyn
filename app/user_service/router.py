"""
Authentication API routes.

Handles user signup and login workflows.
"""
from app.chat_service.services.session_summary_service import generate_session_summary
from fastapi import APIRouter, HTTPException, status,Query
from fastapi import Depends
from app.core.dependencies import get_current_user
from app.chat_service.services.orchestrator.session_lifecycle import end_session
from app.user_service.service import authenticate_user, create_user
from app.core.security import create_access_token
from app.chat_service.utils.logger import get_logger
from app.user_service.schemas import (
    TokenResponse,
    UserLogin,
    UserSignup,
    UserResponse,
)
from app.chat_service.repositories.session_repositories import store_session_summary,get_user_sessions_by_session_id,delete_chat_session
from typing import Optional
import uuid
router = APIRouter(prefix="/auth", tags=["Auth"])

logger = get_logger(__name__)

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(payload: UserSignup) -> UserResponse:
    """
    Register a new user.

    Args:
        payload (UserSignup): User signup payload.

    Returns:
        UserResponse: Created user details.

    Raises:
        HTTPException: If user already exists or internal error occurs.
    """
    try:
        logger.info(
            "Signup request received",
            extra={"email": payload.email},
        )

        return create_user(payload.email, payload.password)

    except ValueError as exc:
        logger.warning(
            "Signup failed",
            extra={"email": payload.email, "reason": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected error during signup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(payload: UserLogin) -> TokenResponse:
    """
    Authenticate user and issue JWT token.
    Session starts here.
    """
    try:
        logger.info(
            "Login attempt",
            extra={"email": payload.email},
        )

        user = authenticate_user(payload.email, payload.password)

        session_id = str(uuid.uuid4())  #  START SESSION

        access_token = create_access_token(
            {
                "sub": user["user_id"],
                "email": user["email"],
                "session_id": session_id,  
            }
        )

        logger.info(
            "Login successful",
            extra={"email": payload.email, "session_id": session_id},
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "session_id": session_id,
        }

    except ValueError:
        ...


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
def logout(
    session_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Logout user and finalize AI session.

    Flow:
    1. Load live session messages
    2. Generate privacy-safe summary
    3. Persist summary
    4. Delete live session memory
    """

    user_id = current_user["sub"]

    if not session_id:
        logger.info(
            "Logout without active session",
            extra={"user_id": user_id},
        )
        return {"message": "Logged out successfully"}

    try:
        # --------------------------------------------------
        # STEP 1: LOAD LIVE SESSION (BEFORE DELETION)
        # --------------------------------------------------
        messages = get_user_sessions_by_session_id(
            user_id=user_id,
            session_id=session_id,
        )

        if messages:
            logger.info(
                "Generating session summary",
                extra={
                    "session_id": session_id,
                    "message_count": len(messages),
                },
            )

            # Adapt your message list to summary format
            session_state = {
                "intents": [m.get("intent") for m in messages if m.get("intent")],
                "emotions": [m.get("emotion") for m in messages if m.get("emotion")],
                "sentiments": [
                    m.get("sentiment") for m in messages if m.get("sentiment")
                ],
            }

            summary = generate_session_summary(session_state)

            store_session_summary(
                session_id=session_id,
                user_id=user_id,
                summary=summary,
            )

        else:
            logger.info(
                "No live messages found, skipping summary",
                extra={"session_id": session_id},
            )

        # --------------------------------------------------
        # STEP 2: DELETE LIVE SESSION MEMORY
        # --------------------------------------------------
        delete_chat_session(
            user_id=user_id,
            session_id=session_id,
        )

        logger.info(
            "Session finalized successfully",
            extra={"session_id": session_id},
        )

    except Exception as exc:
        logger.exception(
            "Session termination failed",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize session",
        )

    return {
        "message": "Logged out successfully",
        "session_id": session_id,
    }
