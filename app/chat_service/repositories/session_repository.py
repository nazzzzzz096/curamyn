"""
Session summary repository.

Handles persistence and deletion of session-level summaries.
"""

from datetime import datetime

from pymongo.errors import PyMongoError

from app.chat_service.utils.logger import get_logger
from app.db.mongodb import get_collection

logger = get_logger(__name__)


def store_session_summary(
    session_id: str,
    user_id: str,
    summary: dict,
) -> None:
    """
    Store a generated session summary in the database.

    Args:
        session_id (str): AI session identifier.
        user_id (str): User identifier.
        summary (dict): Privacy-safe session summary.

    Raises:
        RuntimeError: If database operation fails.
    """
    try:
        collection = get_collection("session_summaries")

        logger.info(
            "Storing session summary",
            extra={"session_id": session_id, "user_id": user_id},
        )

        collection.insert_one(
            {
                "session_id": session_id,
                "user_id": user_id,
                "summary": summary,
                "created_at": datetime.utcnow(),
            }
        )

    except PyMongoError as exc:
        logger.error(
            "Failed to store session summary",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "error": str(exc),
            },
        )
        raise RuntimeError("Failed to store session summary") from exc


def delete_user_sessions(user_id: str) -> int:
    """
    Delete all session summaries for a user.

    Args:
        user_id (str): User identifier.

    Returns:
        int: Number of deleted session documents.

    Raises:
        RuntimeError: If database operation fails.
    """
    try:
        collection = get_collection("session_summaries")

        logger.info(
            "Deleting user session summaries",
            extra={"user_id": user_id},
        )

        result = collection.delete_many({"user_id": user_id})

        logger.info(
            "User session summaries deleted",
            extra={
                "user_id": user_id,
                "deleted_count": result.deleted_count,
            },
        )

        return result.deleted_count

    except PyMongoError as exc:
        logger.error(
            "Failed to delete user session summaries",
            extra={"user_id": user_id, "error": str(exc)},
        )
        raise RuntimeError(
            "Failed to delete user session summaries"
        ) from exc
