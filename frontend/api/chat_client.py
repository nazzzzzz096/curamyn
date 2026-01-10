"""
Chat API client.

Handles interaction with /ai/interact endpoint.
"""

import requests
from typing import Dict

API_BASE_URL = "http://localhost:8000"


def send_message(
    *,
    text: str,
    token: str,
    is_skin: bool = False,
    is_xray: bool = False,
) -> Dict:
    """
    Send chat message to backend.

    Args:
        text: User message
        token: JWT access token
        is_skin: Whether image is skin-related
        is_xray: Whether image is x-ray

    Returns:
        Backend response JSON
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    payload = {
        "input_type": "text",
        "text": text,
        "image_type": "skin" if is_skin else "xray" if is_xray else None,
        "response_mode": "text",
    }

    response = requests.post(
        f"{API_BASE_URL}/ai/interact",
        data=payload,
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            response.json().get("detail", "Chat request failed")
        )

    return response.json()
