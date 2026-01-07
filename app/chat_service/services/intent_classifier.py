"""
Lightweight intent classification using LLM.
Only used when deterministic rules are insufficient.
"""

from app.chat_service.services.llm_service import analyze_text
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

VALID_INTENTS = {
    "self_care",
    "health_support",
    "general_chat",
}


def classify_intent_llm(text: str) -> str:
    """
    Classify user intent using LLM.

    Returns:
        one of: self_care | health_support | general_chat
    """
    prompt = f"""
Classify the user's intent.

Return ONLY one label:
- self_care
- health_support
- general_chat

User message:
{text}
"""

    try:
        result = analyze_text(text=prompt)
        intent = result.get("intent", "").lower()

        if intent in VALID_INTENTS:
            return intent

        logger.warning(
            "Invalid intent returned by LLM",
            extra={"intent": intent},
        )

    except Exception:
        logger.exception("LLM intent classification failed")

    return "general_chat"
