"""
Consent service logic.

Stores and retrieves user consent preferences.
"""

from typing import Dict

from pymongo.errors import PyMongoError

from app.chat_service.utils.logger import get_logger
from app.db.mongodb import get_collection

logger = get_logger(__name__)


def create_or_update_consent(
    user_id: str,
    consent_data: dict,
) -> Dict:
    """
    Create or update consent preferences for a user.

    Args:
        user_id (str): User identifier.
        consent_data (dict): Consent flags.

    Returns:
        Dict: Updated consent document.

    Raises:
        RuntimeError: If database operation fails.
    """
    try:
        collection = get_collection("consent_settings")

        logger.info(
            "Persisting consent preferences",
            extra={"user_id": user_id},
        )

        collection.update_one(
            {"user_id": user_id},
            {"$set": consent_data},
            upsert=True,
        )

        consent_data["user_id"] = user_id
        return consent_data

    except PyMongoError as exc:
        logger.error(
            "Failed to persist consent preferences",
            extra={"user_id": user_id, "error": str(exc)},
        )
        raise RuntimeError("Failed to store consent preferences") from exc


def get_user_consent(user_id: str) -> dict:
    """
    Retrieve user consent preferences.

    Behavior:
    - Returns stored consent if available
    - Returns safe defaults if DB unavailable
    - NEVER raises in request path
    """
    try:
        collection = get_collection("consent_settings")

        consent = collection.find_one(
            {"user_id": user_id},
            {"_id": 0},
        )

        if not consent:
            return {
                "user_id": user_id,
                "voice": False,
                "image": False,
                "document": False,
                "memory": False,
            }

        return consent

    except Exception as exc:
        logger.error(
            "Failed to retrieve consent preferences",
            extra={"user_id": user_id, "error": str(exc)},
        )

        #  SAFE FALLBACK (CI + prod-safe)
        return {
            "user_id": user_id,
            "voice": False,
            "image": False,
            "document": False,
            "memory": False,
        }
