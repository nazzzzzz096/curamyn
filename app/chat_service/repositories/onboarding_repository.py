"""
Onboarding repository.

Handles persistence and retrieval of user onboarding data
stored in the user_profile collection.
"""

from typing import Dict, Optional

from pymongo.errors import PyMongoError

from app.db.mongodb import get_collection
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def get_onboarding_profile(user_id: str) -> Optional[Dict]:
    """
    Fetch onboarding/profile data for a user.

    Args:
        user_id (str): User identifier.

    Returns:
        Optional[Dict]: User onboarding profile (without _id) or None.
    """
    try:
        collection = get_collection("user_profile")

        profile = collection.find_one(
            {"user_id": user_id},
            {"_id": 0},
        )

        if not profile:
            logger.debug(
                "No onboarding profile found",
                extra={"user_id": user_id},
            )

        return profile

    except PyMongoError as exc:
        logger.exception(
            "Failed to fetch onboarding profile",
            extra={"user_id": user_id},
        )
        return None
