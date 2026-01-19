"""
Health advisor LLM service.

Provides supportive, non-diagnostic health guidance
using a single prompt strategy.
"""

import os
import time
import hashlib

import mlflow

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)

PRIMARY_MODEL = "models/gemini-flash-latest"
FALLBACK_MODEL = "models/gemini-flash-lite-latest"


# ==================================================
# SAFE LAZY GEMINI LOADER
# ==================================================
def _load_gemini():
    """Load Gemini client safely (disabled in tests)."""
    if os.getenv("CURAMYN_ENV") == "test":
        return None, None

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("CURAMYN_GEMINI_API_KEY")
        if not api_key:
            return None, None

        return genai.Client(api_key=api_key), GenerateContentConfig

    except Exception as exc:
        logger.warning("Gemini unavailable: %s", exc)
        return None, None


# ==================================================
# PUBLIC ENTRY POINT
# ==================================================
def analyze_health_text(
    *,
    text: str,
    user_id: str | None = None,
    image_context: dict | None = None,
) -> dict:
    """
    Health advisor LLM.

    Uses a single prompt that decides internally whether to:
    - provide reassurance
    - provide self-care steps

    Includes minimal MLflow observability.
    """

    client, GenerateContentConfig = _load_gemini()

    SAFE_FALLBACK = (
        "I am here with you. "
        "Let us take this one step at a time. "
        "You do not have to handle this alone."
    )
    # response to acknowledgement
    if _is_acknowledgement(text):
        logger.info("User acknowledgement detected — minimal response")
        return {
            "intent": "health_support",
            "severity": "informational",
            "response_text": "I’m here with you. Let me know if you need anything.",
        }
    # closure of the conversation
    if _is_closure(text):
        logger.info("Conversation closure detected — stopping guidance")
        return {
            "intent": "health_support",
            "severity": "informational",
            "response_text": "I’m really glad to hear that. Take care, and I’m here if you need me again.",
        }

    # ---------- HARD FALLBACK ----------
    if client is None:
        logger.error("LLM client unavailable")
        return {
            "intent": "health_support",
            "severity": "informational",
            "response_text": SAFE_FALLBACK,
        }

    start_time = time.time()
    wants_steps = any(
        t in text.lower() for t in ["tip", "tips", "suggest", "what can i do", "help"]
    )

    prompt = _build_prompt(text, wants_steps)

    answer = ""
    model_used = None

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "health_advisor_llm")

        # ---------- PRIMARY MODEL ----------
        try:
            response = client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=[
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ],
                config=GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=900,
                    top_p=0.9,
                ),
            )

            candidate = (_extract_text(response) or "").strip()

            if candidate:
                answer = candidate
                model_used = PRIMARY_MODEL
                logger.info("Primary model accepted | length=%s", len(answer))
            else:
                logger.warning("Primary model returned empty text")

        except Exception as exc:
            logger.warning("Primary model failed: %s", exc)

        # ---------- FALLBACK MODEL ----------
        if not answer:
            try:
                response = client.models.generate_content(
                    model=FALLBACK_MODEL,
                    contents=[
                        {
                            "role": "user",
                            "parts": [{"text": prompt}],
                        }
                    ],
                    config=GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=900,
                        top_p=0.9,
                    ),
                )

                candidate = (_extract_text(response) or "").strip()

                if candidate:
                    answer = candidate
                    model_used = PRIMARY_MODEL
                    logger.info("Primary model accepted | length=%s", len(answer))
                else:
                    logger.warning("Primary model returned empty text")

            except Exception as exc:
                logger.exception("Fallback model failed")

        # ---------- FINAL SAFETY ----------
        if not answer:
            logger.warning("LLM returned empty output — using SAFE_FALLBACK")
            answer = SAFE_FALLBACK
            model_used = "safe_fallback"

        # ---------- MLFLOW METRICS ----------
        latency = time.time() - start_time
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)
        mlflow_safe(mlflow.log_metric, "response_length", len(answer))
        mlflow_safe(mlflow.set_tag, "model_used", model_used)

    return {
        "intent": "health_support",
        "severity": "informational",
        "response_text": answer,
    }


# ==================================================
# PROMPT BUILDER (SINGLE PROMPT)
# ==================================================
def _build_prompt(text: str, wants_steps: bool) -> str:
    mode = (
        "Provide 3–5 gentle, practical self-care steps."
        if wants_steps
        else "Provide calm reassurance and supportive presence."
    )

    return f"""
You are Curamyn, a calm and supportive wellbeing assistant.

IMPORTANT:
- You must always respond.
- Never return an empty answer.
- If unsure, provide simple grounding support.

Your task:
{mode}

Guidelines:
- Do not diagnose conditions.
- Do not name medicines or treatments.
- Avoid alarming or clinical language.
- Focus on general wellbeing and comfort.

Response style:
- One short empathetic sentence.
- If steps are requested, list them clearly.
- Simple, human, calm tone.

User message:
{text}

Respond now.
"""


# ==================================================
# RESPONSE TEXT EXTRACTION
# ==================================================
def _extract_text(response) -> str:
    """
    Safely extract text from Gemini responses.

    Handles multiple Gemini response formats.
    """
    if response is None:
        return ""

    # Preferred: candidates -> content -> parts -> text
    candidates = getattr(response, "candidates", None)
    if candidates:
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue

            parts = getattr(content, "parts", None)
            if parts:
                for part in parts:
                    text = getattr(part, "text", None)
                    if isinstance(text, str) and text.strip():
                        return text.strip()

    # Fallback: response.text (sometimes None in Flash)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return ""


def _is_acknowledgement(text: str) -> bool:
    return text.strip().lower() in {
        "ok",
        "okay",
        "thanks",
        "thank you",
        "got it",
        "fine",
        "alright",
        "hmm",
        "huh",
    }


def _is_closure(text: str) -> bool:
    text = text.strip().lower()
    return any(
        phrase in text
        for phrase in [
            "i feel good",
            "feels good now",
            "i am fine",
            "i feel better",
            "thank you",
            "thanks",
            "appreciate it",
            "that helped",
            "i'm okay now",
        ]
    )
