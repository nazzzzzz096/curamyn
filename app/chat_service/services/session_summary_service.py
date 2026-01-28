"""
Session summary generation service.

Creates a privacy-safe, high-level session summary with detailed health context.
This service is ONLY called at session end.

ENHANCED: Now captures specific health topics and contextual details.
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
                temperature=0.0,  # deterministic JSON
                max_output_tokens=1200,  # Increased for detailed summaries
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

    ENHANCED: Now captures specific health topics and contextual details.
    """

    logger.info("Generating enhanced session summary")

    if not messages:
        return _empty_summary()

    transcript = "\n".join(m.strip() for m in messages if m.strip())
    transcript = transcript[:8000]  # Increased limit for better context

    prompt = f"""
You are a SESSION SUMMARY ENGINE for a healthcare AI assistant.

YOU MUST RETURN ONLY VALID JSON.
NO prose. NO markdown. NO explanations.

CRITICAL RULES:
- Health-related content only
- Do NOT give advice or diagnosis
- No personal identifiers (names, addresses, phone numbers)
- Use concise, neutral, clinical language
- CAPTURE SPECIFIC HEALTH CONCERNS mentioned (e.g., "headache", "anxiety", "insomnia")
- INCLUDE CONTEXT DETAILS like duration, triggers, severity, actions taken
- You MUST close all quotes and braces correctly

Conversation Transcript:
{transcript}

Return JSON EXACTLY like this structure:

{{
  "summary_text": "2-3 sentence summary mentioning SPECIFIC health concerns and key context",
  "primary_intent": "health_support | self_care | general_health",
  "primary_emotion": "anxious | stressed | tired | worried | calm | sad | frustrated",
  "overall_sentiment": "negative | neutral | positive",
  "severity_peak": "low | moderate | high",
  "health_topics": ["topic1", "topic2", "topic3"],
  "context_details": {{
    "duration": "how long the issue has persisted (e.g., '3 days', '2 weeks', 'ongoing')",
    "triggers": "what causes or worsens the issue (if mentioned)",
    "severity_notes": "how severe the user describes it",
    "actions_taken": "medications, remedies, doctor visits mentioned (or 'none mentioned')"
  }}
}}

EXAMPLES OF GOOD SUMMARIES:

Example 1 - Headache:
{{
  "summary_text": "User discussed persistent headaches occurring for 3 days, primarily triggered by prolonged screen time and work stress. Expressed concern about impact on work productivity.",
  "primary_intent": "health_support",
  "primary_emotion": "worried",
  "overall_sentiment": "negative",
  "severity_peak": "moderate",
  "health_topics": ["headache", "work stress", "eye strain", "productivity concerns"],
  "context_details": {{
    "duration": "3 days",
    "triggers": "screen time, work deadlines, bright lights",
    "severity_notes": "moderate pain, affecting focus and work",
    "actions_taken": "tried taking breaks, reduced screen brightness"
  }}
}}

Example 2 - Anxiety:
{{
  "summary_text": "User shared ongoing anxiety about upcoming work presentation, experiencing difficulty sleeping for 5 nights. Mentioned trying breathing exercises with limited success.",
  "primary_intent": "health_support",
  "primary_emotion": "anxious",
  "overall_sentiment": "negative",
  "severity_peak": "moderate",
  "health_topics": ["anxiety", "insomnia", "work presentations", "public speaking fear"],
  "context_details": {{
    "duration": "5 nights of poor sleep",
    "triggers": "work presentation, public speaking, fear of judgment",
    "severity_notes": "moderate anxiety, sleep disruption, racing thoughts",
    "actions_taken": "tried breathing exercises, avoided caffeine"
  }}
}}

Example 3 - Multiple Topics:
{{
  "summary_text": "User reported feeling tired and stressed from work, with occasional stomach discomfort. Mentioned irregular sleep schedule affecting overall wellbeing.",
  "primary_intent": "health_support",
  "primary_emotion": "stressed",
  "overall_sentiment": "negative",
  "severity_peak": "low",
  "health_topics": ["fatigue", "work stress", "stomach issues", "sleep disruption"],
  "context_details": {{
    "duration": "past 2 weeks",
    "triggers": "work deadlines, irregular meals, poor sleep schedule",
    "severity_notes": "mild to moderate, manageable but persistent",
    "actions_taken": "none mentioned"
  }}
}}

Example 4 - Positive/Resolution:
{{
  "summary_text": "User followed up on previous anxiety concerns, reported feeling better after implementing suggested relaxation techniques. Sleep quality has improved.",
  "primary_intent": "self_care",
  "primary_emotion": "calm",
  "overall_sentiment": "positive",
  "severity_peak": "low",
  "health_topics": ["anxiety follow-up", "sleep improvement", "relaxation techniques"],
  "context_details": {{
    "duration": "improvement over past week",
    "triggers": "none currently",
    "severity_notes": "resolved or significantly improved",
    "actions_taken": "practicing relaxation techniques, maintaining sleep schedule"
  }}
}}

IMPORTANT GUIDELINES:
1. Be SPECIFIC with health topics - not just "health concern" but "headache", "anxiety", etc.
2. Capture duration details - "3 days", "2 weeks", "ongoing for months"
3. Note triggers if mentioned - "screen time", "work stress", "certain foods"
4. Record actions taken - "tried medication", "saw doctor", "using home remedies"
5. If multiple topics discussed, list all of them
6. If no specific duration/triggers mentioned, leave those fields as "not mentioned"

Now generate the summary:
"""

    try:
        parsed = _generate_summary_llm(prompt=prompt)
    except Exception:
        logger.warning("LLM summary failed; using base summary", exc_info=True)
        return _base_summary_from_transcript(transcript)

    if not parsed:
        return _base_summary_from_transcript(transcript)

    # Validate and structure the response
    return {
        "summary_text": parsed.get("summary_text", ""),
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
        "health_topics": parsed.get("health_topics", []),
        "context_details": parsed.get("context_details", {}),
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
        "health_topics": [],
        "context_details": {},
    }


def _base_summary_from_transcript(transcript: str) -> Dict:
    """
    Fallback summary when LLM fails.
    Uses keyword matching to extract basic health topics.
    """
    text = transcript.lower()

    # Extract basic health topics from text
    health_keywords = {
        "headache": ["headache", "head pain", "migraine"],
        "anxiety": ["anxiety", "anxious", "worried", "nervous", "panic"],
        "insomnia": ["insomnia", "can't sleep", "trouble sleeping"],
        "fatigue": ["tired", "fatigue", "exhausted"],
        "depression": ["sad", "depressed", "depression", "down"],
        "stomach": ["stomach", "nausea", "digestive"],
        "pain": ["pain", "hurt", "ache"],
    }

    detected_topics = []
    for topic, keywords in health_keywords.items():
        if any(kw in text for kw in keywords):
            detected_topics.append(topic)

    return {
        "summary_text": "The user discussed health-related concerns and personal wellbeing.",
        "primary_intent": (
            "self_care"
            if any(w in text for w in ["diet", "sleep", "yoga", "exercise"])
            else "general_health"
        ),
        "primary_emotion": (
            "calm"
            if any(w in text for w in ["calm", "happy", "motivated"])
            else (
                "stressed"
                if any(w in text for w in ["stress", "tired", "anxious"])
                else "neutral"
            )
        ),
        "overall_sentiment": (
            "positive"
            if any(w in text for w in ["happy", "motivated", "better"])
            else (
                "negative"
                if any(w in text for w in ["stress", "tired", "pain"])
                else "neutral"
            )
        ),
        "severity_peak": "low",
        "health_topics": detected_topics if detected_topics else ["general wellness"],
        "context_details": {
            "duration": "not mentioned",
            "triggers": "not mentioned",
            "severity_notes": "not specified",
            "actions_taken": "none mentioned",
        },
    }
