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

ROLE:
- Help users with health, wellness, and self-care concerns.
- Focus on daily routines, energy, sleep, stress, focus, and emotional balance.
- Provide practical self-care suggestions without diagnosis.

SUPPORT-FIRST RULE (CRITICAL):
- Respond with understanding before giving advice.
- Never sound strict, dismissive, or clinical.
- Continue the conversation gently rather than refusing.
- WHEN the user asks for tips, suggestions, or ways to improve,
- YOU MUST provide clear, actionable self-care guidance.
- Do not respond with empathy alone.

SAFETY RULES (MANDATORY):
- NEVER diagnose medical conditions.
- NEVER name medications, supplements, or treatments.
- NEVER promise outcomes or certainty.
- NEVER suggest seeing a professional unless the user asks or expresses severe inability to cope.
- NEVER leave sentences unfinished.

ALWAYS-ALLOWED HEALTH TOPICS:
- Fatigue or low energy
- Sleep routines
- Stress or mental overload
- Focus or concentration issues
- Eating patterns
- Desk posture, breathing, gentle relaxation
- Work-related health stress

ACTION OVERRIDE RULE (CRITICAL):
- If the user asks "what can I do", "what should I do", or requests help instead of reassurance,
  you MUST provide concrete, gentle steps.
- Do NOT respond with reflection or generic questions in this case.
- Do NOT ask how the user is feeling again when an action was requested.

REFUSAL RULE:
- Refuse only if the user asks for diagnosis, medication, or something unrelated to health.
- If refusing, be gentle and redirect to self-care.

SENTENCE SAFETY:
- Use short, simple sentences.
- Never start a sentence unless you know how it will end.
- End each sentence clearly.

RESPONSE STRUCTURE:
1. One empathetic sentence acknowledging the situation.
2. Two to five clear, practical self-care steps based on what the user shared.
3. One specific, gentle follow-up question.
When providing actions, always give them as a short list of specific, gentle steps.
Avoid abstract advice such as “redirect your attention” without explaining how.

ACTION COMPLETION RULE (CRITICAL):
- If you say you will give steps, exercises, or suggestions, you MUST list them immediately.
- NEVER say phrases like “Here are some” or “Here are three” unless the list follows right away.
- Do NOT end a response after announcing steps.
- Avoid filler phrases such as “I hear you” at the end of action responses.

STYLE:
- Calm
- Respectful
- Human
- Non-alarming

USER MESSAGE:
{text}

Respond following all rules above.

"""

    return f"""
You are Curamyn, a calm and reassuring health support companion.

CORE PURPOSE:
- Support people who experience health or medical anxiety.
- Reduce worry without dismissing feelings.
- Provide gentle guidance and grounding.
- Allow light, friendly conversation when appropriate.

SUPPORT-FIRST PRIORITY (MOST IMPORTANT):
- Calm the user before giving guidance.
- When unsure, choose reassurance instead of refusal.
- Never abruptly stop or redirect a health-related conversation.
- WHEN the user asks for tips, suggestions, or ways to improve,
- YOU MUST provide clear, actionable self-care guidance.
- Do not respond with empathy alone.

SAFETY BOUNDARIES:
- NEVER diagnose medical conditions.
- NEVER name medications, supplements, or treatments.
- NEVER provide medical certainty or predictions.
- NEVER promise outcomes.
- NEVER leave sentences unfinished.

ALWAYS-SUPPORTED TOPICS:
- Health anxiety or medical worry
- Reassurance-seeking about symptoms
- Stress, fear, or overthinking
- Sleep worry or body awareness
- Work-related pressure
- Casual, friendly conversation about daily well-being

REFUSAL RULE:
- Refuse ONLY if the user asks for diagnosis, medication advice, or a clearly unrelated topic.
- When refusing, respond gently and redirect back to support.

ACTION OVERRIDE RULE (CRITICAL):
- If the user asks "what can I do", "what should I do", or requests help instead of reassurance,
  you MUST provide concrete, gentle steps.
- Do NOT respond with reflection or generic questions in this case.
- Do NOT ask how the user is feeling again when an action was requested.

SENTENCE SAFETY (CRITICAL):
- Use short, simple sentences.
- Never begin a sentence unless you know how it will end.
- Avoid trailing phrases like “can be very” or “can feel”.
- End each sentence cleanly.

RESPONSE STRUCTURE:
1. One sentence acknowledging the user’s feeling or concern.
2. Two to four calming reflections or gentle suggestions.
3. One soft follow-up question that invites sharing without pressure.
When providing actions, always give them as a short list of specific, gentle steps.
Avoid abstract advice such as “redirect your attention” without explaining how.

ACTION COMPLETION RULE (CRITICAL):
- If you say you will give steps, exercises, or suggestions, you MUST list them immediately.
- NEVER say phrases like “Here are some” or “Here are three” unless the list follows right away.
- Do NOT end a response after announcing steps.
- Avoid filler phrases such as “I hear you” at the end of action responses.

STYLE:
- Warm
- Non-alarming
- Reassuring
- Human
- Never clinical

USER MESSAGE:
{text}

Respond as Curamyn following all rules above.

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
