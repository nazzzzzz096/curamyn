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

import mlflow
from dotenv import load_dotenv

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)
load_dotenv()

MODEL_NAME = "models/gemini-flash-latest"


# --------------------------------------------------
# Test-safe dummy client (so unittest.patch works)
# --------------------------------------------------
class _NullGeminiClient:
    """Safe null Gemini client."""

    class models:
        @staticmethod
        def generate_content(*args, **kwargs):
            return None


# ==================================================
# Lazy Gemini loader
# ==================================================
def _load_gemini():
    """
    Load Gemini client or return a safe null client.
    """
    try:
        # Test env → always null client
        if os.getenv("CURAMYN_ENV") == "test":
            return _NullGeminiClient(), None

        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("CURAMYN_GEMINI_API_KEY")
        if not api_key:
            logger.warning("Gemini API key missing")
            return _NullGeminiClient(), None

        return genai.Client(api_key=api_key), GenerateContentConfig

    except Exception as exc:
        logger.warning("Gemini unavailable: %s", exc)
        return _NullGeminiClient(), None


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

    # Respect patched client in unit tests
    active_client, GenerateContentConfig = _load_gemini()
    start_time = time.time()
    # ---------------- FALLBACK MODE ----------------
    if active_client is None:
        return {
            "intent": "casual_chat",
            "sentiment": "neutral",
            "emotion": "neutral",
            "severity": "low",
            "response_text": "I'm here with you.",
        }

    start_time = time.time()

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "voice_psychologist_llm")
        mlflow_safe(mlflow.set_tag, "pipeline", "voice_and_text")
        mlflow_safe(mlflow.set_tag, "llm_provider", "gemini")

        if user_id:
            mlflow_safe(mlflow.set_tag, "user_id", user_id)

        # -------- STAGE 1: ANALYSIS --------
        try:
            analysis = _analyze_intent(
                text=text,
                client=active_client,
                GenerateContentConfig=GenerateContentConfig,
            )

            severity = analysis.get("severity", "low").lower()
            intent = analysis.get("intent", "casual_chat")
            sentiment = analysis.get("sentiment", "neutral")
            emotion = analysis.get("emotion", "neutral")

        except Exception:
            logger.warning("Intent analysis failed; using defaults")
            severity = "low"
            intent = "casual_chat"
            sentiment = "neutral"
            emotion = "neutral"

        # -------- STAGE 2: RESPONSE --------
        try:
            spoken_text = _generate_spoken_response(
                text=text,
                severity=severity,
                client=active_client,
                GenerateContentConfig=GenerateContentConfig,
            )
        except Exception:
            logger.exception("LLM response generation failed")
            spoken_text = "I'm here with you."

        latency = time.time() - start_time
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)
        mlflow_safe(mlflow.log_param, "severity", severity)

        return {
            "intent": intent,
            "sentiment": sentiment,
            "emotion": emotion,
            "severity": severity,
            "response_text": spoken_text,
        }


# ==================================================
# STAGE 1 — ANALYSIS
# ==================================================
def _analyze_intent(*, text: str, client, GenerateContentConfig) -> dict:
    """
    Analyze user message to extract intent, sentiment, emotion, and severity.

    Uses the Gemini LLM to perform multi-dimensional analysis on the user's input,
    extracting structured metadata about the message. Returns a JSON response parsed
    from the LLM output with analysis results.

    Args:
        text: The user's message to analyze
        client: Gemini API client instance for making requests
        GenerateContentConfig: Gemini configuration class for request parameters

    Returns:
        dict: Analysis results with keys:
            - intent: User's intent (e.g., "casual_chat", "help_request")
            - sentiment: Sentiment polarity (e.g., "positive", "negative", "neutral")
            - emotion: Detected emotion (e.g., "happy", "sad", "anxious")
            - severity: Severity level of the message ("low", "moderate", "high")
    """
    prompt = f"""
Analyze the user's message.

Return ONLY valid JSON with:
intent, sentiment, emotion, severity.

User:
{text}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=(
            GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=600,
            )
            if GenerateContentConfig
            else None
        ),
    )

    raw = _extract_text(response)
    return _safe_json(raw)


# ==================================================
# STAGE 2 — RESPONSE
# ==================================================
def _generate_spoken_response(
    *,
    text: str,
    severity: str,
    client,
    GenerateContentConfig,
) -> str:
    """
    Generate a severity-aware spoken response using the Gemini LLM.

    Selects an appropriate prompt template based on the user's severity level
    (low, moderate, high) and uses the Gemini API to generate a contextually
    appropriate spoken response. Longer responses are validated for minimum length.

    Args:
        text: The user's message or input text to respond to
        severity: Severity level determining tone and length ("low", "moderate", "high")
        client: Gemini API client instance for making requests
        GenerateContentConfig: Gemini configuration class for request parameters

    Returns:
        str: Generated spoken response text, or fallback "I'm here with you."
             if generation fails or response is too short
    """
    PROMPTS = {
        "low": f"""
You are a friendly conversational companion.

IMPORTANT:
- If the user references previous conversations, acknowledge it warmly
- Use any provided context to maintain continuity
- Reply in 2–4 short sentences.

User:
{text}
""",
        "moderate": f"""
You are a calm and understanding listener.

IMPORTANT:
- If the user mentions previous discussions, show you remember
- Reply in 2–3 sentences.

User:
{text}
""",
        "high": f"""
You are a grounding, supportive presence.

IMPORTANT:
- If the user references past conversations, acknowledge it with care
- Reply in 1–2 calm sentences.

User:
{text}
""",
    }

    prompt = PROMPTS.get(severity, PROMPTS["low"])

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=(
            GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=512,
            )
            if GenerateContentConfig
            else None
        ),
    )

    spoken = _extract_text(response)
    if spoken and len(spoken.strip()) > 20:
        return spoken

    return "I'm here with you."


# ==================================================
# HELPERS
# ==================================================
def _extract_text(response) -> str | None:
    """
    Extract text content from a Gemini API response object.

    Attempts multiple strategies to extract text from the response:
    1. Direct text attribute if available
    2. Parse from candidates list structure (standard Gemini response format)
    3. Collect text from multiple parts if response is fragmented

    Args:
        response: Gemini API response object (from generate_content)

    Returns:
        str | None: Extracted and stripped text content, or None if no text found
    """
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


def _safe_json(text: str) -> dict:
    """
    Parse JSON from LLM response text with cleanup and error handling.

    Removes markdown code blocks (```json and ```) and extracts the first JSON
    object found in the text using regex. Validates input and raises descriptive
    errors if parsing fails.

    Args:
        text: String containing JSON text, possibly with markdown formatting

    Returns:
        dict: Parsed JSON object

    Raises:
        ValueError: If input is not a string ("Empty JSON response")
        ValueError: If no JSON object is found in text ("No JSON found")
        json.JSONDecodeError: If extracted text is not valid JSON
    """
    if not isinstance(text, str):
        raise ValueError("Empty JSON response")

    cleaned = re.sub(r"```json|```", "", text, flags=re.I).strip()
    match = re.search(r"\{[\s\S]*?\}", cleaned)

    if not match:
        raise ValueError("No JSON found")

    return json.loads(match.group())
