"""
Summary provider.

Fetches session-level summaries for context agents.
"""

from typing import Optional, Dict
from app.db.mongodb import get_collection
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def get_session_summary(
    *,
    user_id: str,
    session_id: str,
) -> Optional[Dict]:
    """
    Fetch session summary from MongoDB.

    Returns None if summary does not exist.
    """
    collection = get_collection("session_summaries")

    doc = collection.find_one(
        {
            "user_id": user_id,
            "session_id": session_id,
        },
        {"_id": 0, "summary": 1},
    )

    if not doc:
        logger.info(
            "No session summary found",
            extra={"session_id": session_id},
        )
        return None

    logger.info(
        "Session summary loaded",
        extra={"session_id": session_id},
    )

    return doc.get("summary")
