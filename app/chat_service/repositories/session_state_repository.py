"""
Session state persistence in MongoDB.

Stores in-memory session state to survive server restarts.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pymongo.errors import PyMongoError

from app.db.mongodb import get_collection
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def save_session_state(session_id: str, state_data: Dict[str, Any]) -> bool:
    """
    Persist session state to MongoDB.

    Args:
        session_id: Session identifier
        state_data: Complete session state as dict

    Returns:
        bool: True if saved successfully
    """
    try:
        collection = get_collection("session_states")

        collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "state_data": state_data,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        logger.debug(
            "Session state persisted to MongoDB",
            extra={"session_id": session_id},
        )
        return True

    except PyMongoError as exc:
        logger.exception(
            "Failed to persist session state",
            extra={"session_id": session_id},
        )
        return False


def load_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load session state from MongoDB.

    Args:
        session_id: Session identifier

    Returns:
        Optional[Dict]: Session state data or None
    """
    try:
        collection = get_collection("session_states")

        doc = collection.find_one(
            {"session_id": session_id},
            {"_id": 0, "state_data": 1},
        )

        if doc:
            logger.debug(
                "Session state loaded from MongoDB",
                extra={"session_id": session_id},
            )
            return doc.get("state_data")

        return None

    except PyMongoError as exc:
        logger.exception(
            "Failed to load session state",
            extra={"session_id": session_id},
        )
        return None


def delete_session_state(session_id: str) -> bool:
    """
    Delete session state from MongoDB.

    Args:
        session_id: Session identifier

    Returns:
        bool: True if deleted successfully
    """
    try:
        collection = get_collection("session_states")

        result = collection.delete_one({"session_id": session_id})

        logger.info(
            "Session state deleted from MongoDB",
            extra={"session_id": session_id, "deleted": result.deleted_count},
        )
        return result.deleted_count > 0

    except PyMongoError as exc:
        logger.exception(
            "Failed to delete session state",
            extra={"session_id": session_id},
        )
        return False


def cleanup_expired_sessions(expiry_hours: int = 24) -> int:
    """
    Delete session states older than specified hours.

    Args:
        expiry_hours: Delete sessions older than this many hours

    Returns:
        int: Number of deleted sessions
    """
    try:
        from datetime import timedelta

        collection = get_collection("session_states")

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)

        result = collection.delete_many({"updated_at": {"$lt": cutoff_time}})

        deleted_count = result.deleted_count

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} expired session states",
                extra={"expiry_hours": expiry_hours},
            )

        return deleted_count

    except PyMongoError as exc:
        logger.exception("Failed to cleanup expired sessions")
        return 0
