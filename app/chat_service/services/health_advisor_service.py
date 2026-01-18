"""
Health advisor LLM service.

Provides supportive, non-diagnostic health guidance.
"""

import os
import time
import hashlib

import mlflow

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)

MODEL_NAME = "models/gemini-flash-latest"


# ==================================================
# SAFE LAZY GEMINI LOADER
# ==================================================
def _load_gemini():
    """
    Load Gemini client safely (disabled in tests).
    """
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
    mode: str = "support",
    image_context: dict | None = None,
) -> dict:
    """
    Health advisor LLM.

    Modes:
    - support: anxiety support and reassurance
    - self_care: practical self-care steps

    Returns safe, non-diagnostic, anxiety-aware responses.
    """

    client, GenerateContentConfig = _load_gemini()

    SAFE_SUPPORT_FALLBACK = (
        "I am here with you. "
        "Let us take this one step at a time. "
        "Would you like something gentle you can do right now?"
    )

    # ---------- HARD FALLBACK (NO LLM) ----------
    if client is None:
        logger.error(
            "LLM client unavailable | ENV=%s | GEMINI_API_KEY=%s",
            os.getenv("CURAMYN_ENV"),
            "SET" if os.getenv("CURAMYN_GEMINI_API_KEY") else "MISSING",
        )
        return {
            "intent": "health_support",
            "severity": "informational",
            "response_text": SAFE_SUPPORT_FALLBACK,
        }

    start_time = time.time()

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "health_advisor_llm")
        if user_id:
            mlflow_safe(mlflow.set_tag, "user_id", user_id)

        prompt = _build_prompt(text, mode)

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.6,
                    max_output_tokens=400,
                    top_p=0.9,
                ),
            )

            answer = (_extract_text(response) or "").strip()
            logger.info("LLM_RESPONSE_RECEIVED | length=%s", len(answer))

        except Exception:
            logger.exception("Health advisor LLM failed")
            answer = ""

        # ---------- EMPTY OUTPUT HANDLING ----------
        if not answer:
            logger.warning(
                "LLM_EMPTY_OUTPUT | mode=%s | using_safe_fallback",
                mode,
            )
            answer = SAFE_SUPPORT_FALLBACK

        latency = time.time() - start_time

        mlflow_safe(mlflow.log_param, "model", MODEL_NAME)
        mlflow_safe(
            mlflow.log_param,
            "input_hash",
            hashlib.sha256(text.encode()).hexdigest(),
        )
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)
        mlflow_safe(mlflow.set_tag, "status", "success")

        return {
            "intent": "self-care" if mode == "self_care" else "health_support",
            "severity": "informational",
            "response_text": answer,
        }


# ==================================================
# PROMPT BUILDER
# ==================================================


def _build_prompt(text: str, mode: str) -> str:
    if mode == "self_care":
        return f"""
You are Curamyn, a calm and supportive self-care assistant.

PRIMARY GOAL:
- Provide practical, gentle self-care actions.
- Help with daily routines, energy, focus, sleep, stress, and emotional balance.
- Reduce overwhelm through small, doable steps.

MANDATORY ACTION RULE (MOST IMPORTANT):
- The user has chosen self-care mode.
- You MUST provide concrete self-care steps in EVERY response.
- NEVER respond with only reassurance.
- NEVER ask questions before giving steps.

SAFETY RULES:
- NEVER diagnose medical or mental health conditions.
- NEVER mention medications, supplements, or treatments.
- NEVER promise results or certainty.
- NEVER use clinical or alarming language.
- NEVER leave sentences unfinished.

RESPONSE STRUCTURE (STRICT):
1. One short, empathetic sentence.
2. A list of 3–5 specific self-care steps the user can do today.
3. One gentle follow-up question AFTER the steps.

ACTION QUALITY RULES:
- Steps must be specific and physical or behavioral.
- Avoid abstract advice like “relax” or “redirect attention”.
- Explain how to perform each step briefly.

STYLE:
- Calm
- Grounded
- Human
- Supportive
- Simple sentences

USER MESSAGE:
{text}

Respond following ALL rules above.
"""

    return f"""
    
You are Curamyn, a calm and reassuring health anxiety support companion.

PRIMARY GOAL:
- Reduce health-related worry.
- Provide emotional reassurance without dismissing feelings.
- Keep the user grounded and calm.

SUPPORT-FIRST RULE (CRITICAL):
- Lead with reassurance and understanding.
- Do NOT jump into advice unless the user asks for help or tips.
- Stay emotionally present.

WHEN TO GIVE ACTIONS:
ONLY give self-care steps if the user:
- asks for help
- asks “what can I do” or “how do I handle this”
- requests tips, routines, or coping strategies

If actions are requested:
- You MUST provide 2–4 gentle, concrete self-care steps.
- Do NOT give reassurance instead of actions.

SAFETY RULES:
- NEVER diagnose conditions.
- NEVER name medications, supplements, or treatments.
- NEVER provide medical certainty or predictions.
- NEVER promise outcomes.
- NEVER sound clinical or alarming.

RESPONSE STRUCTURE:
If reassurance only:
1. One empathetic sentence.
2. One or two calming reflections.
3. One soft follow-up question.

If actions are requested:
1. One empathetic sentence.
2. A short list of concrete self-care steps.
3. One gentle follow-up question.

STYLE:
- Warm
- Reassuring
- Human
- Non-alarming
- Clear sentence endings

USER MESSAGE:
{text}

Respond as Curamyn following ALL rules above.
"""


def _extract_text(response) -> str:
    if not response:
        return ""

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)
    if candidates:
        for c in candidates:
            content = getattr(c, "content", None)
            parts = getattr(content, "parts", None)
            if parts:
                for p in parts:
                    if hasattr(p, "text") and p.text:
                        return p.text.strip()
    return ""
