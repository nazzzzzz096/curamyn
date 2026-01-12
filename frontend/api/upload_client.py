"""
AI Interaction API client.

Handles sending text, image, and audio inputs to the AI backend.
"""

from typing import Any, Dict, Optional

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class AiInteractionError(RuntimeError):
    """Raised when AI interaction request fails."""


def send_ai_interaction(
    *,
    token: str,
    input_type: str,
    session_id: Optional[str] = None,
    response_mode: str = "text",
    text: Optional[str] = None,
    image_type: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    audio_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Send an interaction request to the AI backend.

    Args:
        token: JWT access token.
        input_type: One of 'text', 'image', 'audio'.
        session_id: Optional chat session ID.
        response_mode: Response mode ('text' or 'voice').
        text: Text input.
        image_type: Image subtype (e.g., 'skin', 'xray').
        file_bytes: Optional image bytes.
        audio_bytes: Optional audio bytes.

    Returns:
        Backend response payload.

    Raises:
        AiInteractionError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/ai/interact"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    data: Dict[str, Any] = {
        "input_type": input_type,
        "response_mode": response_mode,
    }

    if session_id:
        data["session_id"] = session_id
    if text:
        data["text"] = text
    if image_type:
        data["image_type"] = image_type

    files: Dict[str, Any] = {}

    if audio_bytes:
        files["audio"] = (
            "voice.webm",
            audio_bytes,
            "audio/webm",
        )

    if file_bytes:
        files["image"] = (
            "upload.png",
            file_bytes,
            "image/png",
        )

    logger.info(
        "Sending AI interaction",
        extra={
            "input_type": input_type,
            "response_mode": response_mode,
            "has_audio": bool(audio_bytes),
            "has_image": bool(file_bytes),
        },
    )

    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,              # multipart-safe
            files=files or None,    # only include if present
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception(
            "AI interaction request failed",
            extra={"url": url},
        )
        raise AiInteractionError(
            "Failed to communicate with AI service"
        ) from exc

    except ValueError as exc:
        logger.exception(
            "Invalid JSON response from AI backend",
            extra={"url": url},
        )
        raise AiInteractionError(
            "Invalid response received from AI service"
        ) from exc
