"""
LLM service for voice psychologist and general chat.

Performs:
- Intent, sentiment, emotion, severity analysis
- Severity-aware response generation
"""

import os
import re
import json
import time
import hashlib

import mlflow
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

from app.chat_service.utils.logger import get_logger

# --------------------------------------------------
# Setup
# --------------------------------------------------
logger = get_logger(__name__)
load_dotenv()

# --------------------------------------------------
# Environment validation (NEW)
# --------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not configured")

# --------------------------------------------------
# MLflow setup
# --------------------------------------------------
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
mlflow.set_experiment("curamyn_llm_services")

# --------------------------------------------------
# Gemini setup
# --------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-flash-latest"


# ==================================================
# PUBLIC ENTRY POINT
# ==================================================

def analyze_text(
    *,
    text: str,
    user_id: str | None = None,
) -> dict:
    """
    Voice psychologist / general chat LLM.
    """
    start_time = time.time()

    with mlflow.start_run(nested=True):
        mlflow.set_tag("service", "voice_psychologist_llm")
        mlflow.set_tag("pipeline", "voice_and_text")
        mlflow.set_tag("llm_provider", "gemini")

        if user_id:
            mlflow.set_tag("user_id", user_id)

        # ---------------- STAGE 1: SAFE ANALYSIS ---------------- #
        try:
            analysis = _analyze_intent(text)
            severity = analysis.get("severity", "low").lower()
            intent = analysis.get("intent", "casual_chat")
            sentiment = analysis.get("sentiment", "neutral")
            emotion = analysis.get("emotion", "neutral")

        except Exception:
            logger.warning("Intent analysis failed; using safe defaults")
            mlflow.set_tag("analysis_status", "failed")

            severity = "low"
            intent = "casual_chat"
            sentiment = "neutral"
            emotion = "neutral"

        # ---------------- STAGE 2: RESPONSE ---------------- #
        try:
            spoken_text = _generate_spoken_response(text, severity)
        except Exception:
            logger.exception("LLM response generation failed")
            spoken_text = "I’m here with you."

        latency = time.time() - start_time

        mlflow.log_param("severity", severity)
        mlflow.log_metric("latency_sec", latency)
        mlflow.set_tag("status", "success")

        return {
            "intent": intent,
            "sentiment": sentiment,
            "emotion": emotion,
            "severity": severity,
            "response_text": spoken_text,
        }


# ==================================================
# STAGE 1 — ANALYSIS (JSON ONLY)
# ==================================================

def _analyze_intent(text: str) -> dict:
    """
    Analyze user intent and emotional signals.
    Returns JSON only.
    """
    prompt = f"""
Analyze the user's message.

Return ONLY valid JSON with:
intent, sentiment, emotion, severity.

No explanation.
No markdown.
No extra text.

User:
{text}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=150,
        ),
    )

    raw = _extract_text(response)
    return _safe_json(raw)


# ==================================================
# STAGE 2 — RESPONSE (SEVERITY AWARE)
# ==================================================

def _generate_spoken_response(text: str, severity: str) -> str:
    """
    Generate severity-aware conversational response.
    Forces Gemini to always produce natural language output.
    """

    PROMPTS = {
        "low": f"""
You are a friendly conversational companion.

IMPORTANT:
- You MUST reply in plain English
- You MUST speak directly to the user
- Do NOT think silently
- Do NOT analyze internally
- Respond with 2–4 short sentences

Tone:
- Light
- Warm
- Casual

User:
{text}
""",

        "moderate": f"""
You are a calm and understanding listener.

IMPORTANT:
- You MUST reply in plain English
- Empathy only
- No advice
- 2–3 sentences

Tone:
- Gentle
- Reassuring

User:
{text}
""",

        "high": f"""
You are a grounding, supportive presence.

IMPORTANT:
- You MUST reply in plain English
- Focus on emotional safety
- No advice
- 1–2 very calm sentences

User:
{text}
""",
    }


    prompt = PROMPTS.get(severity, PROMPTS["low"])

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=512,
        ),
    )
    logger.warning("RAW GEMINI RESPONSE: %r", response)
    spoken = _extract_text(response)
    if spoken and len(spoken.strip()) > 20:
        return spoken

    logger.warning("Gemini response too short, using fallback")
    return "I'm here with you."



# ==================================================
# HELPERS
# ==================================================

def _extract_text(response) -> str | None:
    """
    Robust Gemini text extraction.
    """

    # 1️⃣ Direct text shortcut
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    # 2️⃣ Candidate-based extraction
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


def _safe_json(text: str) -> dict:
    """
    Safely extract JSON from LLM output.
    """
    if not isinstance(text, str):
        raise ValueError("Empty JSON response")

    cleaned = re.sub(r"```json|```", "", text, flags=re.I).strip()
    match = re.search(r"\{[\s\S]*?\}", cleaned)

    if not match:
        raise ValueError("No JSON found")

    return json.loads(match.group())
