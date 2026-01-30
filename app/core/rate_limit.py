"""
Rate limiting module for the Curamyn application.

- Uses user_id (JWT sub) when authenticated
- Falls back to IP address for unauthenticated requests
- Safe against missing request state
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

import os

if os.getenv("CURAMYN_ENV") == "test":
    limiter = Limiter(key_func=lambda _: "test", default_limits=[])


def user_or_ip(request: Request) -> str:
    """
    Generate rate-limiting key.

    Priority:
    1. Authenticated user ID (JWT sub)
    2. Client IP address
    3. Fallback anonymous key
    """
    try:
        user = getattr(request.state, "user", None)

        if isinstance(user, dict) and "sub" in user:
            return f"user:{user['sub']}"

        ip = get_remote_address(request)
        return f"ip:{ip}" if ip else "anonymous"

    except Exception as exc:
        logger.warning(
            "Rate limit key fallback used",
            extra={"error": str(exc)},
        )
        return "anonymous"


#  Global limiter instance
limiter = Limiter(
    key_func=user_or_ip,
    default_limits=["100/minute"],  # Safety net
)


# --------------------------------------------------
# Optional centralized rate-limit handler
# --------------------------------------------------


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    """
    Custom response when rate limit is exceeded.
    """
    user = getattr(request.state, "user", None)

    logger.warning(
        "Rate limit exceeded",
        extra={
            "path": request.url.path,
            "user_id": user.get("sub") if isinstance(user, dict) else None,
            "ip": get_remote_address(request),
        },
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
        },
    )
