"""
Authentication API routes.

Handles user signup and login workflows.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.security import create_access_token
from app.chat_service.utils.logger import get_logger
from app.user_service.schemas import (
    TokenResponse,
    UserLogin,
    UserSignup,
    UserResponse,
)
from app.user_service.service import authenticate_user, create_user

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


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

    Args:
        payload (UserLogin): Login credentials.

    Returns:
        TokenResponse: JWT access token.

    Raises:
        HTTPException: If authentication fails.
    """
    try:
        logger.info(
            "Login attempt",
            extra={"email": payload.email},
        )

        user = authenticate_user(payload.email, payload.password)

        access_token = create_access_token(
            {"sub": user["user_id"], "email": user["email"]}
        )

        logger.info(
            "Login successful",
            extra={"email": payload.email},
        )

        return TokenResponse(access_token=access_token)

    except ValueError:
        logger.warning(
            "Login failed",
            extra={"email": payload.email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    except Exception as exc:
        logger.exception("Unexpected error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
