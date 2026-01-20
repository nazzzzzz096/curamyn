"""
Consent API client.

Handles fetching and updating user consent preferences.
"""

from typing import Any, Dict

import requests
from requests import RequestException

from frontend.config import settings
from frontend.utils.logger import get_logger


logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class ConsentApiError(RuntimeError):
    """Raised when consent API operations fail."""


def get_consent(*, token: str) -> Dict[str, bool]:
    """
    Fetch user consent settings from the backend.

    Args:
        token: JWT access token.

    Returns:
        A dictionary containing consent flags:
        {
            "memory": bool,
            "voice": bool,
            "document": bool,
            "image": bool
        }

    Raises:
        ConsentApiError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/consent/status"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    logger.info("Fetching user consent")

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        payload = response.json()
        return payload

    except RequestException as exc:
        logger.exception("Failed to fetch user consent")
        raise ConsentApiError("Unable to fetch consent settings") from exc

    except ValueError as exc:
        logger.exception("Invalid response while fetching consent")
        raise ConsentApiError("Invalid consent response received") from exc


def update_consent(*, token: str, consent_data: Dict[str, bool]) -> None:
    """
    Update user consent settings in the backend.

    Args:
        token: JWT access token.
        consent_data: Consent flags to update:
            {
                "memory": bool,
                "voice": bool,
                "document": bool,
                "image": bool
            }

    Raises:
        ConsentApiError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/consent/update"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.info(
        "Updating user consent",
        extra={"consent_keys": list(consent_data.keys())},
    )

    try:
        response = requests.post(
            url,
            headers=headers,
            json=consent_data,
            timeout=10,
        )
        response.raise_for_status()

    except RequestException as exc:
        logger.exception("Failed to update user consent")
        raise ConsentApiError("Unable to update consent settings") from exc

    except ValueError as exc:
        logger.exception("Invalid response while updating consent")
        raise ConsentApiError("Invalid consent update response received") from exc
