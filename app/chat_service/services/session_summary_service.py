"""
Session summary generation service.

Creates a privacy-safe, high-level session summary.
This service is ONLY called at session end.
"""

from typing import Dict

from app.chat_service.utils.logger import get_logger
from app.chat_service.services.llm_service import analyze_text

logger = get_logger(__name__)


def generate_session_summary(session_state: Dict) -> Dict:
    """
    Generate a privacy-safe session summary.

    Rules:
    - No direct quotes
    - No personal identifiers
    - High-level abstraction only
    - Called ONLY at session end
    """
    logger.info("Generating session summary")

    intents = session_state.get("intents", [])
    emotions = session_state.get("emotions", [])
    sentiments = session_state.get("sentiments", [])

    # ---------- EMPTY SESSION GUARD ----------
    if not intents and not emotions and not sentiments:
        logger.warning("Empty session state received for summary")
        return _empty_summary()

    prompt = f"""
You are a system that generates SESSION SUMMARIES.

STRICT RULES:
- Do NOT use user quotes
- Do NOT include personal data
- Do NOT diagnose or advise
- Output valid JSON ONLY

INPUT SIGNALS:
Intents: {intents}
Emotions: {emotions}
Sentiments: {sentiments}

Return JSON exactly with:
summary_text
"""

    try:
        result = analyze_text(text=prompt)

        summary_text = result.get("response_text", "").strip()
        if not summary_text:
            raise ValueError("Empty summary text")

        return {
            "summary_text": summary_text,
        }

    except Exception:
        logger.exception("Failed to generate session summary")
        return _empty_summary()


def _empty_summary() -> Dict:
    """
    Deterministic fallback summary.
    """
    return {
        "summary_text": (
            "The session involved general emotional expression "
            "and supportive conversation without specific concerns."
        )
    }
