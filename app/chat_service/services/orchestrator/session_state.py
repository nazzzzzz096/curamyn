"""
Session state management.

Maintains short-lived, in-memory conversational context per session.
NOTE: This is ephemeral and resets on application restart.
"""

import time
from datetime import datetime,timezone
from typing import Dict, List, Optional

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# In-memory session store
_SESSION_STORE: Dict[str, "SessionState"] = {}

# Session expiration (30 minutes inactivity)
SESSION_TTL_SECONDS = 30 * 60


class SessionState:
    """
    In-memory session state container.

    Stores conversational signals and recent analysis context.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # Conversational memory (signals only)
        self.last_messages: list[dict] = [] 
        self.intents: List[str] = []
        self.severities: List[str] = []
        self.emotions: List[str] = []
        self.sentiments: List[str] = []
        self.started_at= datetime.now(timezone.utc)
        # Image-related context
        self.last_image_analysis: Optional[dict] = None
        self.last_document_text: Optional[str] = None 
        self.recent_topics: list[str] = []
        self.last_user_question: str | None = None
        # Activity tracking
        self.last_activity: float = time.time()
        self.has_health_context: bool = False

    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        """
        Load or create session state.

        Automatically cleans up expired sessions.
        """
        cleanup_expired_sessions()

        if session_id not in _SESSION_STORE:
            logger.info(
                "Creating new session state",
                extra={"session_id": session_id},
            )
            _SESSION_STORE[session_id] = cls(session_id)

        state = _SESSION_STORE[session_id]
        state.touch()
        return state

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    def update_from_llm(self, llm_result: dict) -> None:
        """
       Update session signals based on LLM output.
        """
        if not isinstance(llm_result, dict):
            logger.warning(
            "Invalid LLM result type",
            extra={"session_id": self.session_id},
        )
            return

        intent = llm_result.get("intent") or "health_support"
        if intent:
            self.intents.append(intent)

        #  MARK HEALTH CONTEXT AS ACTIVE (CRITICAL)
            if intent in {
                "health_support",
                "self_care",
                "health_advice",
                "image_analysis",
                "document_understanding",
        }:
                self.has_health_context = True   #

        severity = llm_result.get("severity")
        if severity:
            self.severities.append(severity)

        emotion = llm_result.get("emotion")
        if emotion:
            self.emotions.append(emotion)

        sentiment = llm_result.get("sentiment")
        if sentiment:
            self.sentiments.append(sentiment)



    def update_image_analysis(self, image_analysis: dict) -> None:
        """Store latest medical image analysis context."""
        self.last_image_analysis = image_analysis

    def save(self) -> None:
        """
        Persist session state.

        Currently a no-op as state is in-memory.
        """
        logger.debug(
            "Session state updated",
            extra={"session_id": self.session_id},
        )


def cleanup_expired_sessions() -> None:
    """
    Remove inactive sessions from memory.

    Sessions expire after SESSION_TTL_SECONDS of inactivity.
    """
    now = time.time()
    expired_sessions = [
        session_id
        for session_id, state in _SESSION_STORE.items()
        if now - state.last_activity > SESSION_TTL_SECONDS
    ]

    for session_id in expired_sessions:
        _SESSION_STORE.pop(session_id, None)
        logger.info(
            "Expired session cleared from memory",
            extra={"session_id": session_id},
        )
