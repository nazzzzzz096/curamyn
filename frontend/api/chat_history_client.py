"""
Chat history API client.

Handles fetching chat history and ending chat sessions.
"""

from typing import Any, Dict, List

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class ChatHistoryError(RuntimeError):
    """Raised when chat history operations fail."""


def fetch_chat_history(
    *,
    token: str,
    session_id: str,
) -> List[Dict[str, Any]]:
    """
    Fetch chat history for a session.

    Args:
        token: JWT access token.
        session_id: Chat session identifier.

    Returns:
        List of chat message objects.

    Raises:
        ChatHistoryError: On request or response failure.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    url = f"{API_BASE_URL}/chat/history"

    logger.info(
        "Fetching chat history",
        extra={"session_id": session_id},
    )

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"session_id": session_id},
            timeout=10,
        )
        response.raise_for_status()

        payload = response.json()
        return payload.get("messages", [])

    except RequestException as exc:
        logger.exception(
            "Failed to fetch chat history",
            extra={"session_id": session_id},
        )
        raise ChatHistoryError(
            "Unable to fetch chat history"
        ) from exc

    except ValueError as exc:
        logger.exception(
            "Invalid JSON received while fetching chat history",
            extra={"session_id": session_id},
        )
        raise ChatHistoryError(
            "Invalid response received from server"
        ) from exc


def end_chat_session(
    *,
    token: str,
    session_id: str,
) -> None:
    """
    End an active chat session.

    Args:
        token: JWT access token.
        session_id: Chat session identifier.

    Raises:
        ChatHistoryError: On failure to end session.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    url = f"{API_BASE_URL}/chat/end-session"

    logger.info(
        "Ending chat session",
        extra={"session_id": session_id},
    )

    try:
        response = requests.delete(
            url,
            headers=headers,
            params={"session_id": session_id},
            timeout=10,
        )
        response.raise_for_status()

    except RequestException as exc:
        logger.exception(
            "Failed to end chat session",
            extra={"session_id": session_id},
        )
        raise ChatHistoryError(
            "Unable to end chat session"
        ) from exc
