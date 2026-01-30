"""
Session state management with MongoDB persistence.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.chat_service.utils.logger import get_logger
from app.chat_service.repositories.session_state_repository import (
    save_session_state,
    load_session_state,
    delete_session_state,
)

logger = get_logger(__name__)

# In-memory cache (for performance)
_SESSION_CACHE: Dict[str, "SessionState"] = {}

# Session expiration (30 minutes inactivity)
SESSION_TTL_SECONDS = 30 * 60


class SessionState:
    """
    Session state container with automatic MongoDB persistence.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        #  ENHANCED: Store ALL messages
        self.all_messages: list[dict] = []
        self.last_messages: list[dict] = []

        # Conversational memory
        self.intents: List[str] = []
        self.severities: List[str] = []
        self.emotions: List[str] = []
        self.sentiments: List[str] = []
        self.started_at = datetime.now(timezone.utc)

        # Current conversation state
        self.current_intent: str = "casual_chat"
        self.current_severity: str = "low"
        self.current_emotion: str = "neutral"
        self.current_sentiment: str = "neutral"
        self.current_topic: Optional[str] = None

        #  PERSISTENT: Image context
        self.last_image_analysis: Optional[dict] = None
        self.last_image_type: Optional[str] = None
        self.image_upload_message_index: Optional[int] = None

        #  PERSISTENT: Document context
        self.last_document_text: Optional[str] = None
        self.document_uploaded_at: Optional[float] = None
        self.document_upload_message_index: Optional[int] = None

        # Other context
        self.recent_topics: list[str] = []
        self.last_user_question: str | None = None

        # Activity tracking
        self.last_activity: float = time.time()
        self.has_health_context: bool = False

    def to_dict(self) -> dict:
        """
        Serialize session state to dictionary for MongoDB storage.

        Returns:
            dict: Serializable session state
        """
        return {
            "session_id": self.session_id,
            "all_messages": self.all_messages,
            "last_messages": self.last_messages,
            "intents": self.intents,
            "severities": self.severities,
            "emotions": self.emotions,
            "sentiments": self.sentiments,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "current_intent": self.current_intent,
            "current_severity": self.current_severity,
            "current_emotion": self.current_emotion,
            "current_sentiment": self.current_sentiment,
            "current_topic": self.current_topic,
            "last_image_analysis": self.last_image_analysis,
            "last_image_type": self.last_image_type,
            "image_upload_message_index": self.image_upload_message_index,
            "last_document_text": self.last_document_text,
            "document_uploaded_at": self.document_uploaded_at,
            "document_upload_message_index": self.document_upload_message_index,
            "recent_topics": self.recent_topics,
            "last_user_question": self.last_user_question,
            "last_activity": self.last_activity,
            "has_health_context": self.has_health_context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """
        Deserialize session state from dictionary.

        Args:
            data: Session state dictionary from MongoDB

        Returns:
            SessionState: Restored session state
        """
        state = cls(data["session_id"])

        state.all_messages = data.get("all_messages", [])
        state.last_messages = data.get("last_messages", [])
        state.intents = data.get("intents", [])
        state.severities = data.get("severities", [])
        state.emotions = data.get("emotions", [])
        state.sentiments = data.get("sentiments", [])

        started_at_str = data.get("started_at")
        if started_at_str:
            state.started_at = datetime.fromisoformat(started_at_str)

        state.current_intent = data.get("current_intent", "casual_chat")
        state.current_severity = data.get("current_severity", "low")
        state.current_emotion = data.get("current_emotion", "neutral")
        state.current_sentiment = data.get("current_sentiment", "neutral")
        state.current_topic = data.get("current_topic")

        state.last_image_analysis = data.get("last_image_analysis")
        state.last_image_type = data.get("last_image_type")
        state.image_upload_message_index = data.get("image_upload_message_index")

        state.last_document_text = data.get("last_document_text")
        state.document_uploaded_at = data.get("document_uploaded_at")
        state.document_upload_message_index = data.get("document_upload_message_index")

        state.recent_topics = data.get("recent_topics", [])
        state.last_user_question = data.get("last_user_question")
        state.last_activity = data.get("last_activity", time.time())
        state.has_health_context = data.get("has_health_context", False)

        return state

    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        """
        Load session state from cache or MongoDB.

        Args:
            session_id: Session identifier

        Returns:
            SessionState: Loaded or new session state
        """
        # Check memory cache first (fast)
        if session_id in _SESSION_CACHE:
            state = _SESSION_CACHE[session_id]
            state.touch()
            logger.debug(
                "Loaded session from cache",
                extra={"session_id": session_id},
            )
            return state

        # Try loading from MongoDB (slower)
        state_data = load_session_state(session_id)

        if state_data:
            state = cls.from_dict(state_data)
            _SESSION_CACHE[session_id] = state
            state.touch()
            logger.info(
                "Loaded session from MongoDB",
                extra={"session_id": session_id},
            )
            return state

        # Create new session
        logger.info(
            "Creating new session state",
            extra={"session_id": session_id},
        )
        state = cls(session_id)
        _SESSION_CACHE[session_id] = state
        return state

    def save(self) -> None:
        """
        Persist session state to MongoDB.
        """
        try:
            state_dict = self.to_dict()
            success = save_session_state(self.session_id, state_dict)

            if success:
                logger.debug(
                    "Session state saved to MongoDB",
                    extra={"session_id": self.session_id},
                )
            else:
                logger.warning(
                    "Failed to save session state to MongoDB",
                    extra={"session_id": self.session_id},
                )
        except Exception as exc:
            logger.exception(
                "Error saving session state",
                extra={"session_id": self.session_id},
            )

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to both complete history and recent cache.

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "message_index": len(self.all_messages),
        }

        # Store in complete history
        self.all_messages.append(message)

        # Keep only last 10 in recent cache
        self.last_messages.append(message)
        if len(self.last_messages) > 10:
            self.last_messages.pop(0)

        logger.debug(
            f"Added message to session state",
            extra={
                "session_id": self.session_id,
                "role": role,
                "total_messages": len(self.all_messages),
            },
        )

    def get_conversation_window(self, max_messages: int = 15) -> list[dict]:
        """Get a sliding window of recent conversation."""
        return self.all_messages[-max_messages:] if self.all_messages else []

    def get_condensed_history(self) -> str:
        """Get a condensed summary of older messages."""
        if len(self.all_messages) <= 15:
            return ""

        older_messages = self.all_messages[:-15]
        topics_discussed = set()

        for msg in older_messages:
            content = msg.get("content", "").lower()
            health_keywords = [
                "headache",
                "pain",
                "stress",
                "anxiety",
                "sleep",
                "tired",
                "fatigue",
                "nausea",
                "fever",
                "cough",
                "document",
                "report",
                "x-ray",
                "image",
            ]

            for keyword in health_keywords:
                if keyword in content:
                    topics_discussed.add(keyword)

        if topics_discussed:
            return f"Earlier in conversation, discussed: {', '.join(topics_discussed)}"

        return "Earlier conversation covered general health topics"

    # ... (keep all other existing methods like update_from_llm, clear_document_context, etc.)

    def clear_document_context(self) -> None:
        """
        Clear document-related context.
        Called when user moves to a different topic.
        """
        self.last_document_text = None
        self.document_uploaded_at = None
        self.document_upload_message_index = None
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
        """Update session signals based on LLM output."""
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

        if severity in ["moderate", "high"] and self.all_messages:
            last_user_msg = None
            for msg in reversed(self.all_messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "").lower()
                    break

            if last_user_msg:
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
        """Get current conversation context for prompt building."""
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
        """Persist session state (currently in-memory)."""
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
        for session_id, state in _SESSION_CACHE.items()
        if now - state.last_activity > SESSION_TTL_SECONDS
    ]

    for session_id in expired_sessions:
        _SESSION_CACHE.pop(session_id, None)
        logger.info(
            "Expired session cleared from memory",
            extra={"session_id": session_id},
        )
