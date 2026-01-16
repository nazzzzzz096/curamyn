"""
Chat session and session summary repository.

Handles:
- Chat message persistence (chat_sessions)
- Session summaries persistence (session_summaries)
"""

from datetime import datetime, timezone
from typing import List, Dict

from pymongo.errors import PyMongoError

from app.chat_service.utils.logger import get_logger
from app.db.mongodb import get_collection

logger = get_logger(__name__)


# =================================================
# SESSION SUMMARY
# =================================================


def store_session_summary(
    session_id: str,
    user_id: str,
    summary: dict,
) -> None:
    """
    Store a generated session summary in MongoDB.

    Args:
        session_id: AI session identifier.
        user_id: User identifier.
        summary: Privacy-safe session summary.

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
                "created_at": datetime.now(timezone.utc),
            }
        )

        logger.info(
            "Session summary stored successfully",
            extra={
                "db": collection.database.name,
                "collection": collection.name,
            },
        )

    except PyMongoError as exc:
        logger.exception(
            "Failed to store session summary",
            extra={"session_id": session_id, "user_id": user_id},
        )
        raise RuntimeError("Failed to store session summary") from exc


def delete_user_sessions(user_id: str) -> int:
    """
    Delete all session summaries for a user.

    Args:
        user_id: User identifier.

    Returns:
        int: Number of deleted documents.
    """
    logger.info("Deleting session summaries", extra={"user_id": user_id})

    try:
        collection = get_collection("session_summaries")
        result = collection.delete_many({"user_id": user_id})
        deleted = result.deleted_count or 0

        logger.info(
            "Session summaries deleted",
            extra={"user_id": user_id, "deleted_count": deleted},
        )
        return deleted

    except PyMongoError as exc:
        logger.error(
            "Failed to delete session summaries",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return 0


# =================================================
# CHAT SESSIONS
# =================================================


def get_chat_messages_for_session(
    user_id: str,
    session_id: str,
) -> List[Dict]:
    """
    Fetch chat messages for a single user session.

    Args:
        user_id: User identifier.
        session_id: Session identifier.

    Returns:
        List of chat message dictionaries.
    """
    try:
        collection = get_collection("chat_sessions")

        doc = collection.find_one(
            {"user_id": user_id, "session_id": session_id},
            {"_id": 0, "messages": 1},
        )

        messages = doc.get("messages", []) if doc else []

        logger.info(
            "Chat messages fetched",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "count": len(messages),
                "sample": messages[0] if messages else None,
            },
        )

        return messages

    except PyMongoError as exc:
        logger.exception(
            "Failed to fetch chat messages",
            extra={"user_id": user_id, "session_id": session_id},
        )
        return []


# Backward compatibility alias
get_user_sessions_by_session_id = get_chat_messages_for_session


def append_chat_message(
    user_id: str,
    session_id: str,
    message: Dict,
) -> None:
    """
    Append a chat message to a session.

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        message: Normalized chat message.
    """
    try:
        collection = get_collection("chat_sessions")

        collection.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )

        logger.debug(
            "Chat message appended",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "author": message.get("author"),
            },
        )

    except PyMongoError as exc:
        logger.exception(
            "Failed to append chat message",
            extra={"user_id": user_id, "session_id": session_id},
        )
        raise


def delete_chat_session(user_id: str, session_id: str) -> None:
    """
    Delete a single chat session.

    Args:
        user_id: User identifier.
        session_id: Session identifier.
    """
    try:
        collection = get_collection("chat_sessions")
        collection.delete_one({"user_id": user_id, "session_id": session_id})

        logger.info(
            "Chat session deleted",
            extra={"user_id": user_id, "session_id": session_id},
        )

    except PyMongoError as exc:
        logger.exception(
            "Failed to delete chat session",
            extra={"user_id": user_id, "session_id": session_id},
        )
        raise


def delete_chat_sessions_by_user(user_id: str) -> int:
    """
    Delete all chat sessions for a user.
    """
    logger.info("Deleting chat sessions", extra={"user_id": user_id})

    try:
        collection = get_collection("chat_sessions")
        result = collection.delete_many({"user_id": user_id})
        deleted = result.deleted_count or 0

        logger.info(
            "Chat sessions deleted",
            extra={"user_id": user_id, "deleted_count": deleted},
        )
        return deleted

    except PyMongoError as exc:
        logger.exception(
            "Failed to delete chat sessions",
            extra={"user_id": user_id},
        )
        return 0
