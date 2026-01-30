"""
Authentication API routes.

Handles user signup and login workflows.
"""

from app.chat_service.services.session_summary_service import generate_session_summary
from fastapi import APIRouter, HTTPException, status, Query, Request
from fastapi import Depends
from app.core.dependencies import get_current_user
from app.chat_service.services.orchestrator.session_lifecycle import end_session
from app.user_service.service import authenticate_user, create_user
from app.core.security import create_access_token
from app.common.audit_logger import log_login
from app.chat_service.utils.logger import get_logger
from app.user_service.schemas import (
    TokenResponse,
    UserLogin,
    UserSignup,
    UserResponse,
)
from app.chat_service.repositories.session_repositories import (
    store_session_summary,
    delete_chat_session,
    get_chat_messages_for_session,
)
from typing import Optional
import uuid
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = get_logger(__name__)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("2/minute")
def signup(request: Request, payload: UserSignup) -> UserResponse:
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


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: UserLogin) -> TokenResponse:
    """Authenticate user and issue JWT token."""

    ip_address = getattr(request.state, "ip_address", "unknown")
    user_agent = getattr(request.state, "user_agent", "unknown")

    try:
        user = authenticate_user(payload.email, payload.password)

        session_id = str(uuid.uuid4())

        access_token = create_access_token(
            {
                "sub": user["user_id"],
                "email": user["email"],
                "session_id": session_id,
            }
        )

        #  AUDIT LOG: Successful login
        log_login(
            user_id=user["user_id"],
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        logger.info("Login successful", extra={"email": payload.email})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "session_id": session_id,
        }

    except ValueError:
        #  AUDIT LOG: Failed login
        log_login(
            user_id=payload.email,  # Use email since we don't have user_id
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
        )

        logger.warning("Login failed", extra={"email": payload.email})

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("2/minute")
def logout(
    request: Request,
    session_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Logout user and finalize AI session.

    Flow:
    1. Load live session messages
    2. Generate privacy-safe summary from conversation
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
        messages = get_chat_messages_for_session(
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

            #  CHANGE STARTS HERE
            # Extract ONLY user messages for summarization
            user_messages = [
                m.get("text", "").strip()
                for m in messages
                if m.get("author") == "You"
                and m.get("type") == "text"
                and m.get("text")
            ]

            print("user_messages", user_messages)
            summary = generate_session_summary(messages=user_messages)
            #  CHANGE ENDS HERE

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
