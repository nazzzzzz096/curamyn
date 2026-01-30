"""
FastAPI authentication dependencies.

Provides the current authenticated user from JWT tokens.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.chat_service.utils.logger import get_logger
from app.core.security import verify_access_token
import sentry_sdk

logger = get_logger(__name__)

security = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Retrieve the currently authenticated user.

    Args:
        credentials (HTTPAuthorizationCredentials): Bearer token credentials.

    Returns:
        dict: Decoded JWT payload.

    Raises:
        HTTPException: If token is invalid or expired.
    """

    """
    Retrieve the currently authenticated user.
    """

    token = credentials.credentials

    try:
        user = verify_access_token(token)
        request.state.user = user

        #  Add user context to Sentry
        sentry_sdk.set_user(
            {
                "id": user.get("sub"),
                "email": user.get("email"),
            }
        )

        logger.info("Authenticated user request", extra={"user_id": user.get("sub")})
        return user

    except ValueError as exc:
        logger.warning("Authentication failed")

        #  Capture failed auth in Sentry
        sentry_sdk.capture_exception(exc)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
