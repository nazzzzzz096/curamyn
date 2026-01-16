"""
Memory API client.

Handles user memory deletion requests from the frontend.
"""

from typing import Any, Dict

import requests
from requests import RequestException

from frontend.config import settings
from frontend.state.app_state import state
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class MemoryApiError(RuntimeError):
    """Raised when memory-related API operations fail."""


def delete_memory() -> Dict[str, Any]:
    """
    Delete all stored user memory from the backend.

    Returns:
        Backend response payload.

    Raises:
        MemoryApiError: If user is not authenticated or deletion fails.
    """
    if not state.token:
        logger.warning("Memory deletion attempted without authentication")
        raise MemoryApiError("User not authenticated")

    url = f"{API_BASE_URL}/memory/clear"

    headers = {
        "Authorization": f"Bearer {state.token}",
        "Accept": "application/json",
    }

    logger.info("Deleting user memory")

    try:
        response = requests.delete(
            url,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception(
            "Failed to delete user memory",
            extra={"url": url},
        )
        raise MemoryApiError("Unable to delete user memory") from exc

    except ValueError as exc:
        logger.exception(
            "Invalid response while deleting memory",
            extra={"url": url},
        )
        raise MemoryApiError("Invalid response received from server") from exc
