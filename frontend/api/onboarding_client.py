"""
Questions API client.

Handles fetching the next question and submitting answers.
"""

from typing import Any, Dict, Optional

import requests
from requests import RequestException

from frontend.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = settings.API_BASE_URL


class QuestionsApiError(RuntimeError):
    """Raised when question-related API operations fail."""


def get_next_question(*, token: str) -> Dict[str, Any]:
    """
    Fetch the next question for the user.

    Args:
        token: JWT access token.

    Returns:
        A dictionary containing the next question payload.

    Raises:
        QuestionsApiError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/questions/next"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    logger.info("Fetching next question")

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception("Failed to fetch next question")
        raise QuestionsApiError(
            "Unable to fetch next question"
        ) from exc

    except ValueError as exc:
        logger.exception("Invalid response received for next question")
        raise QuestionsApiError(
            "Invalid response from questions service"
        ) from exc


def submit_answer(
    *,
    token: str,
    question_key: str,
    answer: Optional[str],
) -> Dict[str, Any]:
    """
    Submit an answer for a question.

    Args:
        token: JWT access token.
        question_key: Unique key identifying the question.
        answer: User's answer (may be None).

    Returns:
        Backend response payload.

    Raises:
        QuestionsApiError: On request or backend failure.
    """
    url = f"{API_BASE_URL}/questions/answer"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "question_key": question_key,
        "answer": answer,
    }

    logger.info(
        "Submitting answer",
        extra={"question_key": question_key},
    )

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except RequestException as exc:
        logger.exception(
            "Failed to submit answer",
            extra={"question_key": question_key},
        )
        raise QuestionsApiError(
            "Unable to submit answer"
        ) from exc

    except ValueError as exc:
        logger.exception("Invalid response received after submitting answer")
        raise QuestionsApiError(
            "Invalid response from questions service"
        ) from exc
