"""
Background task to cleanup expired sessions.

Run this as a cron job or scheduled task.
"""

from app.chat_service.repositories.session_state_repository import (
    cleanup_expired_sessions,
)
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def cleanup_job():
    """
    Cleanup expired session states from MongoDB.

    Should be run periodically (e.g., hourly).
    """
    logger.info("Starting session cleanup job")

    deleted_count = cleanup_expired_sessions(expiry_hours=24)

    logger.info(
        f"Session cleanup completed: {deleted_count} sessions deleted",
        extra={"deleted_count": deleted_count},
    )


if __name__ == "__main__":
    cleanup_job()


# Edit crontab
# crontab -e

# Add this line (runs cleanup every hour)
# 0 * * * * cd /path/to/curamyn && /path/to/venv/bin/python -m app.tasks.cleanup_sessions >> /var/log/curamyn_cleanup.log 2>&1
