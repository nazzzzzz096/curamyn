"""
Chat Summary API client.

Handles saving a summary of the chat session when the user logs out.
"""

from typing import Any, Dict

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class ChatSummaryError(RuntimeError):
    """Raised when saving chat summary fails."""


def save_chat_summary(*, token: str, summary: str) -> None:
    """
    Save chat summary to the backend.

    Args:
        token: JWT access token.
        summary: Chat summary text.

    Raises:
        ChatSummaryError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/chat/summary"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.info(
        "Saving chat summary",
        extra={"summary_length": len(summary)},
    )

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"summary": summary},
            timeout=10,
        )
        response.raise_for_status()

    except RequestException as exc:
        logger.exception(
            "Failed to save chat summary",
            extra={"url": url},
        )
        raise ChatSummaryError(
            "Unable to save chat summary"
        ) from exc

    except ValueError as exc:
        logger.exception(
            "Invalid response while saving chat summary",
            extra={"url": url},
        )
        raise ChatSummaryError(
            "Invalid response received from server"
        ) from exc

