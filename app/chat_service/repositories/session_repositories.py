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
        collection = get_collection("session_summaries")

        logger.info(
         "Mongo target info",
          extra={
        "db_name": collection.database.name,
        "collection_name": collection.name,
        },
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


from pymongo.errors import PyMongoError

def delete_user_sessions(user_id: str) -> int:
    """
    Delete all session summaries for a user.

    Behavior:
    - Returns number of deleted documents on success
    - Returns 0 if storage is unavailable
    - NEVER raises in request path (CI / prod safe)

    Args:
        user_id (str): User identifier.

    Returns:
        int: Number of deleted session documents.
    """
    logger.info(
        "Deleting user session summaries",
        extra={"user_id": user_id},
    )

    try:
        collection = get_collection("session_summaries")
        result = collection.delete_many({"user_id": user_id})

        deleted = result.deleted_count or 0

        logger.info(
            "User session summaries deleted",
            extra={
                "user_id": user_id,
                "deleted_count": deleted,
            },
        )

        return deleted

    except PyMongoError as exc:
        logger.error(
            "Failed to delete user session summaries",
            extra={"user_id": user_id, "error": str(exc)},
        )

        #  Safe fallback (CI + prod)
        return 0

def get_user_sessions_by_session_id(user_id: str, session_id: str) -> list:
    """
    Load live chat messages for a session (used on refresh).
    """
    try:
        collection = get_collection("chat_sessions")

        doc = collection.find_one(
            {
                "user_id": user_id,
                "session_id": session_id,
            },
            {"_id": 0, "messages": 1},
        )

        if not doc:
            return []

        return doc.get("messages", [])

    except PyMongoError as exc:
        logger.error(
            "Failed to fetch chat session",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "error": str(exc),
            },
        )
        return []
def append_chat_message(user_id: str, session_id: str, message: dict):
    collection = get_collection("chat_sessions")

    collection.update_one(
        {
            "user_id": user_id,
            "session_id": session_id,
        },
        {
            "$push": {"messages": message},
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )
def delete_chat_session(user_id: str, session_id: str):
    collection = get_collection("chat_sessions")
    collection.delete_one(
        {"user_id": user_id, "session_id": session_id}
    )
