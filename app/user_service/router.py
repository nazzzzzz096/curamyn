"""
Authentication API routes.

Handles user signup and login workflows.
"""

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

    - Triggers session summarization if memory consent is enabled
    - Clears in-memory session state
    """

    if session_id:
        try:
            end_session(
                session_id=session_id,
                user_id=current_user["sub"],
            )
        except Exception as exc:
            logger.exception(
                "Session termination failed",
                extra={
                    "user_id": current_user["sub"],
                    "session_id": session_id,
                    "error": str(exc),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to finalize session",
            )
    else:
        
        logger.info(
            "Logout without active session",
            extra={"user_id": current_user["sub"]},
        )

    logger.info(
        "User logged out successfully",
        extra={
            "user_id": current_user["sub"],
            "session_id": session_id,
        },
    )

    return {
        "message": "Logged out successfully",
        "session_id": session_id,
    }

