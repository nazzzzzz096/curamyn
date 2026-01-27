"""
Session state management.

Maintains short-lived, in-memory conversational context per session.
NOTE: This is ephemeral and resets on application restart.

✅ ENHANCED: Now tracks current conversation state (intent, severity, emotion, topic)
"""

import time
from datetime import datetime, timezone
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

     NEW: Tracks current state for better context continuity.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # Conversational memory (signals only)
        self.last_messages: list[dict] = []
        self.intents: List[str] = []
        self.severities: List[str] = []
        self.emotions: List[str] = []
        self.sentiments: List[str] = []
        self.started_at = datetime.now(timezone.utc)

        #  NEW: Current conversation state (for context continuity)
        self.current_intent: str = "casual_chat"
        self.current_severity: str = "low"
        self.current_emotion: str = "neutral"
        self.current_sentiment: str = "neutral"
        self.current_topic: Optional[str] = None  # e.g., "work stress", "sleep issues"

        # Image-related context
        self.last_image_analysis: Optional[dict] = None
        self.last_document_text: Optional[str] = None
        self.document_uploaded_at: Optional[float] = None
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

    def clear_document_context(self) -> None:
        """
        Clear document-related context.
        Called when user moves to a different topic.
        """
        self.last_document_text = None
        self.document_uploaded_at = None
        logger.info("Document context cleared", extra={"session_id": self.session_id})

    def is_document_context_stale(self, max_age_seconds: int = 300) -> bool:
        """
        Check if document context is too old (default 5 minutes).

        Args:
            max_age_seconds: Maximum age in seconds before context is stale

        Returns:
            True if context should be cleared
        """
        if not self.document_uploaded_at:
            return False

        age = time.time() - self.document_uploaded_at
        return age > max_age_seconds

    def update_from_llm(self, llm_result: dict) -> None:
        """
        Update session signals based on LLM output.

         ENHANCED: Now updates current state for better context continuity.
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
            self.current_intent = intent

            # MARK HEALTH CONTEXT AS ACTIVE (CRITICAL)
            if intent in {
                "health_support",
                "self_care",
                "health_advice",
                "image_analysis",
                "document_understanding",
            }:
                self.has_health_context = True

        severity = llm_result.get("severity")
        if severity:
            self.severities.append(severity)
            self.current_severity = severity

        emotion = llm_result.get("emotion")
        if emotion:
            self.emotions.append(emotion)
            self.current_emotion = emotion

        sentiment = llm_result.get("sentiment")
        if sentiment:
            self.sentiments.append(sentiment)
            self.current_sentiment = sentiment

        #  NEW: Extract topic from user's last message if severity is moderate/high
        if severity in ["moderate", "high"] and self.last_messages:
            last_user_msg = None
            for msg in reversed(self.last_messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "").lower()
                    break

            if last_user_msg:
                # Simple topic extraction from keywords
                if "stress" in last_user_msg or "stressed" in last_user_msg:
                    self.current_topic = "stress"
                elif "sleep" in last_user_msg or "insomnia" in last_user_msg:
                    self.current_topic = "sleep issues"
                elif "anxious" in last_user_msg or "anxiety" in last_user_msg:
                    self.current_topic = "anxiety"
                elif "work" in last_user_msg:
                    self.current_topic = "work stress"
                elif "tired" in last_user_msg or "fatigue" in last_user_msg:
                    self.current_topic = "fatigue"
                elif "sad" in last_user_msg or "depressed" in last_user_msg:
                    self.current_topic = "low mood"

    def get_current_context(self) -> dict:
        """
         NEW: Get current conversation context for prompt building.

        Returns:
            Dict with current intent, severity, emotion, and topic
        """
        return {
            "intent": self.current_intent,
            "severity": self.current_severity,
            "emotion": self.current_emotion,
            "sentiment": self.current_sentiment,
            "topic": self.current_topic,
            "has_health_context": self.has_health_context,
        }

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
