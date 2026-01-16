"""
Onboarding question service.

Handles question progression and answer persistence.
"""

from typing import Dict, Optional
from datetime import datetime, timezone
from app.chat_service.utils.logger import get_logger
from app.db.mongodb import get_collection

logger = get_logger(__name__)


ONBOARDING_QUESTIONS = [
    {
        "key": "gender",
        "question": "Would you like to share your gender? (Optional, you may skip)",
    },
    {
        "key": "age_range",
        "question": "Which age range do you belong to? (Optional, you may skip)",
    },
    {
        "key": "known_conditions",
        "question": "Do you have any known medical conditions? (Optional, you may skip)",
    },
    {
        "key": "medications",
        "question": "Are you currently taking any medications? (Optional, you may skip)",
    },
    {
        "key": "emotional_baseline",
        "question": "How do you usually feel emotionally? (Optional, you may skip)",
    },
]

VALID_KEYS = {q["key"] for q in ONBOARDING_QUESTIONS}


def get_next_question(user_id: str) -> Dict:
    """
    Retrieve the next unanswered onboarding question.

    Args:
        user_id (str): User identifier.

    Returns:
        Dict: Question payload or completion state.
    """

    logger.info("Determining next onboarding question", extra={"user_id": user_id})

    profiles = get_collection("user_profile")
    profile = profiles.find_one({"user_id": user_id}) or {}

    for question in ONBOARDING_QUESTIONS:
        if question["key"] not in profile:
            return {
                "question_key": question["key"],
                "question_text": question["question"],
                "completed": False,
            }

    return {
        "question_key": None,
        "question_text": None,
        "completed": True,
    }


def save_answer(
    user_id: str,
    question_key: str,
    answer: str,
) -> Dict:
    """
    Save a user's answer to an onboarding question.

    Args:
        user_id (str): User identifier.
        question_key (str): Question key.
        answer (str): User response or 'skip'.

    Returns:
        Dict: Next onboarding question.

    Raises:
        ValueError: If question key is invalid.
    """

    if question_key not in VALID_KEYS:
        raise ValueError("Invalid question key")

    profiles = get_collection("user_profile")

    cleaned = (answer or "").strip()
    normalized_answer: Optional[str] = (
        None if cleaned == "" or cleaned.lower() == "skip" else cleaned
    )

    logger.info(
        "Saving onboarding response",
        extra={
            "user_id": user_id,
            "question_key": question_key,
            "skipped": normalized_answer is None,
        },
    )

    profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                question_key: normalized_answer,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    return get_next_question(user_id)
