"""
Session summary generation service.

Creates a privacy-safe, high-level session summary.
This service is ONLY called at session end.
"""
from typing import Dict, List
import json

from app.chat_service.utils.logger import get_logger
from app.chat_service.services.llm_service import analyze_text

logger = get_logger(__name__)


def generate_session_summary(session_state: Dict) -> Dict:
    """
    Generate a privacy-safe session summary.

    Called ONLY at session end.
    """
    logger.info("Generating session summary")

    intents: List[str] = session_state.get("intents", [])
    emotions: List[str] = session_state.get("emotions", [])
    sentiments: List[str] = session_state.get("sentiments", [])

    # ---------- EMPTY SESSION GUARD ----------
    if not intents and not emotions and not sentiments:
        logger.warning("Empty session state received for summary")
        return _empty_summary()

    # Deduplicate signals
    unique_intents = sorted(set(intents))
    unique_emotions = sorted(set(emotions))
    unique_sentiments = sorted(set(sentiments))

    prompt = f"""
You are a system that generates SESSION SUMMARIES.

STRICT RULES:
- Do NOT quote the user
- Do NOT include personal data
- Do NOT diagnose or advise
- Output VALID JSON ONLY

INPUT SIGNALS:
Intents: {unique_intents}
Emotions: {unique_emotions}
Sentiments: {unique_sentiments}

Return JSON exactly in this schema:

{{
  "summary_text": "<high-level summary>"
}}
"""

    try:
        result = analyze_text(text=prompt)
        raw_text = result.get("response_text", "").strip()

        if not raw_text:
            raise ValueError("Empty LLM output")

        #  Safe JSON parsing
        parsed = _safe_parse_json(raw_text)

        summary_text = parsed.get("summary_text")
        if not summary_text:
            raise ValueError("Missing summary_text")

        return {
            "summary_text": summary_text,
            "intent_observed": unique_intents,
            "emotion_observed": unique_emotions,
            "sentiment_observed": unique_sentiments,
        }

    except Exception as exc:
        logger.exception(
            "Failed to generate session summary",
            extra={"error": str(exc)},
        )
        return _empty_summary()


def _safe_parse_json(text: str) -> Dict:
    """
    Safely parse JSON from LLM output.
    Handles markdown-wrapped JSON.
    """
    try:
        text = text.strip()

        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()

        return json.loads(text)

    except Exception:
        logger.warning("Failed to parse JSON, falling back")
        return {}
def _empty_summary() -> Dict:
    return {
        "summary_text": (
            "The session involved general interaction without "
            "distinct conversational signals."
        ),
        "intent_observed": [],
        "emotion_observed": [],
        "sentiment_observed": [],
    }
