"""
Session lifecycle management.

Handles session termination, summarization,
and cleanup of in-memory session state.
"""

from datetime import datetime

from app.chat_service.services.orchestrator.session_state import (
    _SESSION_STORE,
)
from app.chat_service.services.session_summary_service import (
    generate_session_summary,
)
from app.chat_service.repositories.session_repositories import (
    store_session_summary,
)
from app.consent_service.service import get_user_consent
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def end_session(*, session_id: str, user_id: str) -> None:
    """
    Finalize a session.

    - Generate summary if memory consent is granted
    - Persist summary + metadata
    - Delete full in-memory session state

    This function is called ONLY on logout.
    """
    state = _SESSION_STORE.get(session_id)

    if not state:
        logger.info(
            "No in-memory session found to end",
            extra={"session_id": session_id},
        )
        return

    consent = get_user_consent(user_id)

    if consent.get("memory"):
        try:
            summary = generate_session_summary(state.__dict__)

            store_session_summary(
                session_id=session_id,
                user_id=user_id,
                summary={
                    **summary,
                    "ended_at": datetime.utcnow(),
                },
            )

            logger.info(
                "Session summary stored",
                extra={"session_id": session_id},
            )

        except Exception as exc:
            logger.exception(
                "Failed to store session summary",
                extra={"session_id": session_id, "error": str(exc)},
            )

    #  Always delete session memory
    _SESSION_STORE.pop(session_id, None)

    logger.info(
        "Session memory cleared",
        extra={"session_id": session_id},
    )
