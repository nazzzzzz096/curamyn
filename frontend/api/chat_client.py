"""
Chat API client.

Handles interaction with the /ai/interact backend endpoint.
"""

from typing import Any, Dict

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class ChatRequestError(RuntimeError):
    """Raised when chat interaction with backend fails."""


def send_message(
    *,
    text: str,
    token: str,
    is_skin: bool = False,
    is_xray: bool = False,
) -> Dict[str, Any]:
    """
    Send a chat message to the backend AI interaction endpoint.

    Args:
        text: User input message.
        token: JWT access token.
        is_skin: Whether the image is skin-related.
        is_xray: Whether the image is x-ray related.

    Returns:
        Backend response JSON.

    Raises:
        ChatRequestError: On request or backend failure.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    payload = {
        "input_type": "text",
        "text": text,
        "image_type": ("skin" if is_skin else "xray" if is_xray else None),
        "response_mode": "text",
    }

    url = f"{API_BASE_URL}/ai/interact"

    logger.info(
        "Sending chat message",
        extra={
            "endpoint": "/ai/interact",
            "has_token": bool(token),
            "image_type": payload["image_type"],
        },
    )

    try:
        response = requests.post(
            url,
            json=payload,  # IMPORTANT: json, not data
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception(
            "Chat request failed",
            extra={"url": url},
        )
        raise ChatRequestError("Failed to communicate with AI service") from exc

    except ValueError as exc:
        logger.exception(
            "Invalid JSON response from backend",
            extra={"url": url},
        )
        raise ChatRequestError("Invalid response received from AI service") from exc
