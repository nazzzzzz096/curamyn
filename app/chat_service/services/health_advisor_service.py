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
    - support: emotional reassurance
    - self_care: practical self-care tips

    Returns non-diagnostic, safe responses only.
    """
    client, GenerateContentConfig = _load_gemini()
    logger.error(
    "ENV CHECK | ENV=%s | GEMINI_API_KEY=%s",
    os.getenv("CURAMYN_ENV"),
    "SET" if os.getenv("CURAMYN_GEMINI_API_KEY") else "MISSING",
    )

    # ---------------- FALLBACK MODE ----------------
    if client is None:
        return {
            "intent": "health_advice",
            "severity": "informational",
            "response_text": (
                "I'm here to support you. "
                "If this concern continues, it may help to speak with a healthcare professional."
            ),
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
                ),
            )
            answer = _extract_text(response)
            answer = (answer or "").strip()
            logger.warning("SELF_CARE LLM OUTPUT: %s", answer)
            if not answer:
                logger.warning("Gemini returned no visible text — retrying with forced output")

                force_prompt = f"""
Reply ONLY with plain text.
No safety explanations.
No refusal.
No meta commentary.

User message:
{text}

Start writing now.
"""

                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=force_prompt,
                    config=GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=400
                    ),
                )

                answer = _extract_text(response)


        except Exception:
            logger.exception("Health advisor LLM failed")
            mlflow_safe(mlflow.set_tag, "status", "failed")
            answer = ""

        if not answer:
            answer = (
                "I'm here to support you. "
                "If this concern continues, it may help to speak with a healthcare professional."
            )

        latency = time.time() - start_time
        if not answer.endswith((".", "!", "?")):
            answer += ". Please let me know how you are feeling right now."
        mlflow_safe(mlflow.log_param, "model", MODEL_NAME)
        mlflow_safe(
            mlflow.log_param,
            "input_hash",
            hashlib.sha256(text.encode()).hexdigest(),
        )
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)
        mlflow_safe(mlflow.set_tag, "status", "success")

        return {
            "intent": "self-care" if mode== "self-care" else "health_support",
            "severity": "informational",
            "response_text": answer,
        }


# ==================================================
# PROMPT BUILDER
# ==================================================

def _build_prompt(text: str, mode: str) -> str:
    if mode == "self_care":
        return f"""
You are Curamyn, a HEALTH-ONLY self-care assistant.

STRICT RULES (MANDATORY):
- ONLY discuss health, wellness, and self-care
- NEVER answer general knowledge questions
- NO diagnosis
- NO medication names
- ALL sentences must be complete
- NO unfinished bullet points
- NO vague reassurance
- if you can't complete the sentence just add something related to it which doesn't affect the flow of conversation.

RESPONSE STRUCTURE (REQUIRED):
1. One empathetic sentence (complete)
2. 3–5 clear bullet-point self-care steps
3. One short follow-up question about health

IMPORTANT COMPLETION RULE:
- If a sentence starts but cannot be completed safely, you MUST finish it with a neutral, supportive ending.
- Never leave a sentence grammatically incomplete.
- Prefer safe endings such as:
  "are valid."
  "are understandable."
  "are common when dealing with health concerns."


REDIRECTION TEMPLATE (use if off-topic):
"I'm here to help with health and self-care only. If you'd like, we can focus on steps that may help you feel better."

USER MESSAGE:
{text}

Provide a COMPLETE response using the structure above.


"""

    #  SUPPORT MODE (THIS WAS MISSING)
    return f"""
You are a HEALTH SUPPORT assistant.

ROLE:
- Provide emotional reassurance
- Help the user move forward
- Stay strictly within health-related topics

STRICT RULES:
- NEVER diagnose
- NEVER give medication names
- NEVER answer non-health questions
- NEVER trail off mid-sentence
- ALWAYS provide a next step
- if you can't complete the sentence just add something related to it which doesn't affect the flow of conversation.
SUPPORT MODE BEHAVIOR:
1. Acknowledge how the user is feeling (1 sentence)
2. Reassure without minimizing concerns (1 sentence)
3. Suggest a practical, safe next step (1 sentence)
4. Ask ONLY ONE concrete follow-up question related to symptoms

IMPORTANT COMPLETION RULE:
- If a sentence starts but cannot be completed safely, you MUST finish it with a neutral, supportive ending.
- Never leave a sentence grammatically incomplete.
- Prefer safe endings such as:
  "are valid."
  "are understandable."
  "are common when dealing with health concerns."

DO NOT:
- Ask vague questions
- Ask multiple questions
- Change the topic
- Continue the conversation without direction

USER MESSAGE:
{text}

Respond in 3–5 complete sentences following the structure above.


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
