"""
Chat Summary API client.

Saves a summary of the chat when the user logs out.
"""

import requests
from frontend.config import settings


def save_chat_summary(token: str, summary: str) -> None:
    """
    Save chat summary to backend.

    Args:
        token (str): JWT access token
        summary (str): Chat summary text

    Raises:
        RuntimeError: If saving fails
    """
    response = requests.post(
        f"{settings.API_BASE_URL}/chat/summary",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"summary": summary},
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            response.json().get("detail", "Failed to save chat summary")
        )

