"""
Session summary generation service.

Creates a privacy-safe, high-level session summary.
This service is ONLY called at session end.
"""

from typing import List, Dict
import json
import re
import time
import os

import mlflow
from dotenv import load_dotenv

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)
load_dotenv()

MODEL_NAME = "models/gemini-flash-latest"

# ==================================================
# INTERNAL LLM LOADER (SUMMARY ONLY)
# ==================================================
def _load_gemini():
    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("CURAMYN_GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing Gemini API key")

        return genai.Client(api_key=api_key), GenerateContentConfig

    except Exception as exc:
        logger.warning("Gemini unavailable for summary: %s", exc)
        return None, None


# ==================================================
# INTERNAL SUMMARY LLM
# ==================================================
def _generate_summary_llm(*, prompt: str) -> Dict:
    """
    Dedicated LLM call for session summary.
    NEVER used for chat or intent detection.
    """

    client, GenerateContentConfig = _load_gemini()
    if client is None:
        raise RuntimeError("Summary LLM unavailable")

    start_time = time.time()

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "session_summary_llm")
        mlflow_safe(mlflow.set_tag, "llm_provider", "gemini")

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.0,        # deterministic JSON
                max_output_tokens=800,  # prevent truncation
            ),
        )

        raw = _extract_text(response)
        if not raw:
            raise ValueError("Empty summary LLM output")

        mlflow_safe(
            mlflow.log_metric,
            "summary_latency_sec",
            time.time() - start_time,
        )

        return _safe_parse_json(raw)


# ==================================================
# PUBLIC API 
# ==================================================
def generate_session_summary(messages: List[str]) -> Dict:
    """
    Generate a privacy-safe session summary from conversation messages.
    Called ONLY at logout.
    """

    logger.info("Generating session summary")

    if not messages:
        return _empty_summary()

    transcript = "\n".join(m.strip() for m in messages if m.strip())
    transcript = transcript[:6000]  # hard safety cap

    prompt = f"""
You are a SESSION SUMMARY ENGINE.

YOU MUST RETURN ONLY VALID JSON.
NO prose. NO markdown. NO explanations.

RULES:
- Health-related only
- Do NOT give advice or diagnosis
- No personal identifiers
- Use concise neutral language
- You MUST close all quotes and braces

Conversation:
{transcript}

Return JSON EXACTLY like this:
{{
  "summary_text": "2 to 3 sentence neutral summary",
  "primary_intent": "health_support | self_care | general_health",
  "primary_emotion": "anxious | stressed | tired | worried | calm",
  "overall_sentiment": "negative | neutral | positive",
  "severity_peak": "low | moderate | high"
}}
"""

    try:
        parsed = _generate_summary_llm(prompt=prompt)
    except Exception:
        logger.warning("LLM summary failed; using base summary", exc_info=True)
        return _base_summary_from_transcript(transcript)

    if not parsed:
        return _base_summary_from_transcript(transcript)

    return {
        "summary_text": parsed.get("summary_text"),
        "primary_intent": _safe_enum(
            parsed.get("primary_intent"),
            {"health_support", "self_care", "general_health"},
        ),
        "primary_emotion": parsed.get("primary_emotion"),
        "overall_sentiment": _safe_enum(
            parsed.get("overall_sentiment"),
            {"positive", "neutral", "negative"},
            default="neutral",
        ),
        "severity_peak": _safe_enum(
            parsed.get("severity_peak"),
            {"low", "moderate", "high"},
            default="low",
        ),
    }


# ==================================================
# HELPERS
# ==================================================
def _extract_text(response) -> str | None:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)
    if not candidates:
        return None

    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None)
    if not isinstance(parts, list):
        return None

    collected = [
        p.text.strip()
        for p in parts
        if hasattr(p, "text") and isinstance(p.text, str) and p.text.strip()
    ]
    return " ".join(collected) if collected else None


def _safe_parse_json(text: str) -> Dict:
    if not text:
        return {}

    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)

    if not match:
        return {}

    try:
        return json.loads(match.group())
    except Exception:
        return {}


def _safe_enum(value, allowed, default=None):
    return value if value in allowed else default


def _empty_summary() -> Dict:
    return {
        "summary_text": (
            "The session involved limited or low-signal health-related interaction "
            "without sustained discussion."
        ),
        "primary_intent": None,
        "primary_emotion": None,
        "overall_sentiment": None,
        "severity_peak": None,
    }


def _base_summary_from_transcript(transcript: str) -> Dict:
    text = transcript.lower()

    return {
        "summary_text": "The user discussed health-related thoughts and personal well-being.",
        "primary_intent": (
            "self_care" if any(w in text for w in ["diet", "sleep", "yoga", "exercise"])
            else "general_health"
        ),
        "primary_emotion": (
            "calm" if any(w in text for w in ["calm", "happy", "motivated"])
            else "stressed" if any(w in text for w in ["stress", "tired", "anxious"])
            else None
        ),
        "overall_sentiment": (
            "positive" if any(w in text for w in ["happy", "motivated"])
            else "negative" if any(w in text for w in ["stress", "tired"])
            else "neutral"
        ),
        "severity_peak": "low",
    }
