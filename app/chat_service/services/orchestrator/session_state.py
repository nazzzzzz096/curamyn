"""
Session state management.

Maintains short-lived, in-memory conversational context per session.
NOTE: This is ephemeral and resets on application restart.
"""

from typing import Dict, List, Optional

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

_SESSION_STORE: Dict[str, "SessionState"] = {}


class SessionState:
    """
    In-memory session state container.

    Stores conversational signals and recent analysis context.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # Conversational memory (signals only)
        self.intents: List[str] = []
        self.severities: List[str] = []
        self.emotions: List[str] = []
        self.sentiments: List[str] = []

        # Image-related context
        self.last_image_analysis: Optional[dict] = None

    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        """
        Load or create session state.

        Args:
            session_id (str): Session identifier.

        Returns:
            SessionState: Session instance.
        """
        if session_id not in _SESSION_STORE:
            logger.info(
                "Creating new session state",
                extra={"session_id": session_id},
            )
            _SESSION_STORE[session_id] = cls(session_id)

        return _SESSION_STORE[session_id]

    def update_from_llm(self, llm_result: dict) -> None:
        """
        Update session signals based on LLM output.

        Args:
            llm_result (dict): LLM response payload.
        """
        if not isinstance(llm_result, dict):
            logger.warning("Invalid LLM result type")
            return

        if "intent" in llm_result:
            self.intents.append(llm_result["intent"])

        if "severity" in llm_result:
            self.severities.append(llm_result["severity"])

        if "emotion" in llm_result:
            self.emotions.append(llm_result["emotion"])

        if "sentiment" in llm_result:
            self.sentiments.append(llm_result["sentiment"])

    def update_image_analysis(self, image_analysis: dict) -> None:
        """
        Store latest medical image analysis context.
        """
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
