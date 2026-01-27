"""
Health advisor LLM service.

 ENHANCED: Now uses session context (severity, emotion, topic) for better continuity
"""

import os
import time

import mlflow

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)

PRIMARY_MODEL = "models/gemini-flash-latest"
FALLBACK_MODEL = "models/gemini-flash-lite-latest"


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


def analyze_health_text(
    *,
    text: str,
    user_id: str | None = None,
    image_context: dict | None = None,
    session_context: dict | None = None,
) -> dict:
    """
    Health advisor LLM with context awareness.

    Args:
        text: User's message
        user_id: Optional user identifier
        image_context: Optional image analysis context
        session_context:  NEW - Current conversation state (severity, emotion, topic)

    Returns:
        Dict with intent, severity, emotion, and response_text
    """

    client, GenerateContentConfig = _load_gemini()

    SAFE_FALLBACK = (
        "I am here with you. "
        "Let us take this one step at a time. "
        "You do not have to handle this alone."
    )

    # Simple acknowledgments get minimal responses
    if _is_acknowledgement(text):
        logger.info("User acknowledgement detected — minimal response")
        return {
            "intent": "health_support",
            "severity": (
                session_context.get("severity", "low") if session_context else "low"
            ),
            "response_text": "I'm here with you. Let me know if you need anything.",
        }

    # Conversation closure
    if _is_closure(text):
        logger.info("Conversation closure detected")
        return {
            "intent": "health_support",
            "severity": "low",
            "response_text": "I'm really glad to hear that. Take care, and I'm here if you need me again.",
        }

    if client is None:
        logger.error("LLM client unavailable")
        return {
            "intent": "health_support",
            "severity": "informational",
            "response_text": SAFE_FALLBACK,
        }

    start_time = time.time()
    wants_steps = any(
        t in text.lower()
        for t in ["tip", "tips", "suggest", "what can i do", "help", "advice"]
    )

    #  Build prompt with session context
    prompt = _build_prompt(text, wants_steps, session_context)

    answer = ""
    model_used = None

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "health_advisor_llm")

        # Log context if available
        if session_context:
            mlflow_safe(mlflow.set_tag, "has_context", "true")
            mlflow_safe(
                mlflow.set_tag, "context_severity", session_context.get("severity")
            )
            mlflow_safe(mlflow.set_tag, "context_topic", session_context.get("topic"))

        # PRIMARY MODEL
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

        # FALLBACK MODEL
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
                    model_used = FALLBACK_MODEL
                    logger.info("Fallback model accepted | length=%s", len(answer))
                else:
                    logger.warning("Fallback model returned empty text")

            except Exception as exc:
                logger.exception("Fallback model failed")

        # FINAL SAFETY
        if not answer:
            logger.warning("LLM returned empty output — using SAFE_FALLBACK")
            answer = SAFE_FALLBACK
            model_used = "safe_fallback"

        # MLFLOW METRICS
        latency = time.time() - start_time
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)
        mlflow_safe(mlflow.log_metric, "response_length", len(answer))
        mlflow_safe(mlflow.set_tag, "model_used", model_used)

    return {
        "intent": "health_support",
        "severity": _infer_severity(text, session_context),
        "emotion": (
            session_context.get("emotion", "neutral") if session_context else "neutral"
        ),
        "response_text": answer,
    }


def _build_prompt(text: str, wants_steps: bool, context: dict = None) -> str:
    """
     ENHANCED: Build prompt with session context awareness.

    Args:
        text: Current user message
        wants_steps: Whether user wants practical tips
        context: Session context with severity, emotion, topic
    """

    #  Build context block if we have previous state
    context_block = ""
    if context and context.get("severity") not in ["low", "informational", None]:
        context_lines = []

        if context.get("emotion") and context.get("emotion") != "neutral":
            context_lines.append(
                f"User's current emotional state: {context.get('emotion')}"
            )

        if context.get("severity"):
            context_lines.append(f"Conversation severity: {context.get('severity')}")

        if context.get("topic"):
            context_lines.append(f"Current topic: {context.get('topic')}")

        if context_lines:
            context_block = (
                "\n\n[CONTEXT FROM PREVIOUS MESSAGES]\n"
                + "\n".join(context_lines)
                + "\n"
            )

    #  Adapt mode based on whether we have context
    if wants_steps:
        if context and context.get("topic"):
            mode = f"Provide 3–5 gentle, practical steps specifically to help with their {context.get('topic')}."
        else:
            mode = "Provide 3–5 gentle, practical self-care steps."
    else:
        mode = "Provide a warm, empathetic, and conversational response."

    return f"""
You are Curamyn, a warm, empathetic, and supportive wellbeing companion.
{context_block}
Your personality:
- Kind, caring, and genuinely interested in the person's wellbeing
- Speak naturally like a supportive friend
- Offer encouragement, validation, and gentle suggestions
- You can think deeply and respond thoughtfully - no constraints

IMPORTANT:
- ALWAYS respond - never return empty
- When someone greets you (hello, hi, hey), respond warmly
- If they ask for tips/suggestions AND you have context about their situation, provide relevant tips
- If they mention previous topics, acknowledge the continuity
- Match your response depth to their emotional state

Your task:
{mode}

Guidelines:
- Do NOT diagnose medical conditions
- Do NOT name medicines or treatments
- Avoid alarming language
- Focus on wellbeing, comfort, emotional support
- If context shows they're struggling, be extra gentle and supportive

Response style:
- Natural, flowing conversation
- Express genuine care
- Ask gentle follow-up questions when appropriate
- Warm, personal, human tone

User message:
{text}

Respond thoughtfully:
"""


def _infer_severity(text: str, context: dict = None) -> str:
    """
     Infer severity with context awareness.

    If user says "give me tips" but context shows moderate/high severity,
    maintain that severity level.
    """
    text_lower = text.lower()

    # If just asking for tips but we have existing severity context
    if any(word in text_lower for word in ["tips", "suggestions", "advice", "help"]):
        if context and context.get("severity") in ["moderate", "high"]:
            return context.get("severity")

    # Otherwise, infer from current message
    crisis_words = ["suicide", "kill myself", "can't go on", "want to die"]
    high_words = ["can't cope", "overwhelming", "can't breathe", "panic"]
    moderate_words = ["stressed", "anxious", "worried", "struggling", "tired"]

    if any(word in text_lower for word in crisis_words):
        return "high"
    if any(word in text_lower for word in high_words):
        return "high"
    if any(word in text_lower for word in moderate_words):
        return "moderate"

    return "low"


def _extract_text(response) -> str:
    """Safely extract text from Gemini responses."""
    if response is None:
        return ""

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

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return ""


def _is_acknowledgement(text: str) -> bool:
    """Check if text is simple acknowledgment (not greeting)."""
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
        "sure",
        "yep",
        "yeah",
    }


def _is_closure(text: str) -> bool:
    """Check if user is ending conversation positively."""
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
            "feeling better",
        ]
    )
