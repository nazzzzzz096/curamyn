"""
Authentication API client for frontend.

Handles communication with backend authentication endpoints.
"""

from typing import Any, Dict, Optional

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

BACKEND_BASE_URL = settings.API_BASE_URL


class AuthenticationError(RuntimeError):
    """Raised when authentication-related operations fail."""


def _post(
    endpoint: str,
    *,
    json_data: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Internal helper to perform POST requests with error handling.

    Raises:
        AuthenticationError: On request or response failure.
    """
    url = f"{BACKEND_BASE_URL}{endpoint}"

    try:
        response = requests.post(
            url,
            json=json_data,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception(
            "HTTP request failed",
            extra={"url": url, "payload": json_data},
        )
        raise AuthenticationError("Backend request failed") from exc

    except ValueError as exc:
        logger.exception(
            "Invalid JSON response",
            extra={"url": url},
        )
        raise AuthenticationError("Invalid response from server") from exc


def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user via backend API.

    Args:
        email: User email.
        password: User password.

    Returns:
        JSON response containing access token.

    Raises:
        AuthenticationError: On authentication failure.
    """
    logger.info("Attempting user login", extra={"email": email})

    return _post(
        "/auth/login",
        json_data={"email": email, "password": password},
    )


def signup_user(email: str, password: str) -> Dict[str, Any]:
    """
    Register a new user via backend API.

    Args:
        email: User email.
        password: User password.

    Returns:
        Created user payload.

    Raises:
        AuthenticationError: On signup failure.
    """
    logger.info("Attempting user signup", extra={"email": email})

    return _post(
        "/auth/signup",
        json_data={"email": email, "password": password},
    )


def logout_user(token: str, session_id: Optional[str] = None) -> None:
    """
    Logout a user via backend API.

    Args:
        token: Bearer token.
        session_id: Optional session identifier.

    Raises:
        AuthenticationError: On logout failure.
    """
    logger.info("Attempting user logout", extra={"session_id": session_id})

    headers = {"Authorization": f"Bearer {token}"}
    params = {"session_id": session_id} if session_id else None

    _post(
        "/auth/logout",
        headers=headers,
        params=params,
    )
