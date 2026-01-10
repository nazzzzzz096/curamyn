"""
Consent API client.

Handles fetching and updating user consent preferences.
"""

import requests
from frontend.config import settings


def get_consent(token: str) -> dict:
    """
    Fetch user consent settings from backend.

    Returns:
        dict:
        {
            "memory": bool,
            "voice": bool,
            "document": bool,
            "image": bool
        }
    """
    response = requests.get(
        f"{settings.API_BASE_URL}/consent/status",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            response.json().get("detail", "Failed to fetch consent")
        )

    return response.json()


def update_consent(token: str, consent_data: dict) -> None:
    """
    Update user consent settings in backend.

    Args:
        consent_data (dict):
        {
            "memory": bool,
            "voice": bool,
            "document": bool,
            "image": bool
        }
    """
    response = requests.post(
        f"{settings.API_BASE_URL}/consent/update",
        json=consent_data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            response.json().get("detail", "Failed to update consent")
        )
