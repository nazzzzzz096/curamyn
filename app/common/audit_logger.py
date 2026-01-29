"""
HIPAA-compliant audit logging.

Logs all data access, modifications, and security events.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

from app.db.mongodb import get_collection
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""

    # Authentication
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_SIGNUP = "user_signup"
    AUTH_FAILED = "auth_failed"

    # Data Access
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_ACCESSED = "document_accessed"
    IMAGE_UPLOADED = "image_uploaded"
    IMAGE_ACCESSED = "image_accessed"

    # Chat Events
    CHAT_MESSAGE_SENT = "chat_message_sent"
    CHAT_MESSAGE_RECEIVED = "chat_message_received"
    CHAT_HISTORY_ACCESSED = "chat_history_accessed"

    # Consent Management
    CONSENT_UPDATED = "consent_updated"
    CONSENT_ACCESSED = "consent_accessed"

    # Data Deletion
    MEMORY_DELETED = "memory_deleted"
    SESSION_DELETED = "session_deleted"

    # Security Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class AuditLogger:
    """
    HIPAA-compliant audit logger.

    All events are:
    - Immutable (append-only)
    - Timestamped
    - Linked to user/session
    - Detailed with context
    """

    @staticmethod
    def log_event(
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> bool:
        """
        Log an audit event to MongoDB.

        Args:
            event_type: Type of event
            user_id: User who performed the action
            session_id: Session identifier
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional event details
            success: Whether the action was successful

        Returns:
            bool: True if logged successfully
        """
        try:
            collection = get_collection("audit_logs")

            audit_entry = {
                "event_type": event_type.value,
                "user_id": user_id,
                "session_id": session_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {},
                "success": success,
                "timestamp": datetime.now(timezone.utc),
            }

            # Insert into append-only collection
            collection.insert_one(audit_entry)

            logger.debug(
                f"Audit event logged: {event_type.value}",
                extra={
                    "event_type": event_type.value,
                    "user_id": user_id,
                    "success": success,
                },
            )

            return True

        except Exception as exc:
            # CRITICAL: If audit logging fails, log to stderr
            logger.critical(
                f"AUDIT LOGGING FAILED: {event_type.value}",
                extra={
                    "event_type": event_type.value,
                    "user_id": user_id,
                    "error": str(exc),
                },
            )
            return False


# Convenience functions
def log_login(user_id: str, ip_address: str, user_agent: str, success: bool = True):
    """Log user login attempt."""
    AuditLogger.log_event(
        event_type=AuditEventType.USER_LOGIN if success else AuditEventType.AUTH_FAILED,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )


def log_document_upload(
    user_id: str,
    session_id: str,
    ip_address: str,
    document_size: int,
    document_type: str,
):
    """Log document upload."""
    AuditLogger.log_event(
        event_type=AuditEventType.DOCUMENT_UPLOADED,
        user_id=user_id,
        session_id=session_id,
        ip_address=ip_address,
        details={
            "document_size": document_size,
            "document_type": document_type,
        },
    )


def log_chat_access(user_id: str, session_id: str, ip_address: str):
    """Log chat history access."""
    AuditLogger.log_event(
        event_type=AuditEventType.CHAT_HISTORY_ACCESSED,
        user_id=user_id,
        session_id=session_id,
        ip_address=ip_address,
    )


def log_memory_deletion(user_id: str, session_id: str, ip_address: str):
    """Log memory deletion."""
    AuditLogger.log_event(
        event_type=AuditEventType.MEMORY_DELETED,
        user_id=user_id,
        session_id=session_id,
        ip_address=ip_address,
    )
