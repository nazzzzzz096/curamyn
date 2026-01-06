"""
JWT security utilities.

Handles access token creation and verification.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict

from dotenv import load_dotenv
from jose import JWTError, jwt

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


if not SECRET_KEY:
    logger.critical("JWT_SECRET not configured")
    raise RuntimeError("JWT_SECRET environment variable is required")


def create_access_token(data: Dict) -> str:
    """
    Create a JWT access token.

    Args:
        data (Dict): Payload to encode (e.g. user identifiers).

    Returns:
        str: Encoded JWT token.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})

    logger.debug(
        "Creating access token",
        extra={"expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES},
    )

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_access_token(token: str) -> Dict:
    """
    Verify and decode a JWT access token.

    Args:
        token (str): JWT token.

    Returns:
        Dict: Decoded token payload.

    Raises:
        ValueError: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        logger.debug(
            "Token successfully verified",
            extra={"subject": payload.get("sub")},
        )

        return payload

    except JWTError as exc:
        logger.warning(
            "Token verification failed",
            extra={"error": str(exc)},
        )
        raise ValueError("Invalid or expired token") from exc

