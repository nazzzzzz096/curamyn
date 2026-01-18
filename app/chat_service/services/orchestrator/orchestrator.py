"""
Main orchestration pipeline for handling user interactions.

This module coordinates:
- Input routing
- Safety checks
- LLM invocation
- Session state updates
- Response building
"""

from typing import Any, Dict

from app.chat_service.services.orchestrator.input_router import route_input
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.services.orchestrator.response_builder import build_response
from app.chat_service.services.voice_pipeline_service import voice_chat_pipeline

from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.health_advisor_service import analyze_health_text
from app.chat_service.services.ocr_llm_service import analyze_ocr_text
from app.chat_service.services.intent_classifier import classify_intent_llm
from app.chat_service.services.context_agent.context_agent import ContextAgent
from app.chat_service.services.safety_guard import (
    check_input_safety,
    check_output_safety,
    detect_emergency,
    SafetyViolation,
)

from app.consent_service.service import get_user_consent
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_DENY_CONSENT: Dict[str, bool] = {
    "voice": False,
    "image": False,
    "document": False,
    "memory": False,
}


async def run_interaction(
    *,
    input_type: str,
    session_id: str,
    user_id: str | None,
    text: str | None,
    audio: bytes | None,
    image: bytes | None,
    image_type: str | None,
    response_mode: str,
) -> Dict[str, Any]:
    """
    Orchestrates a single user interaction lifecycle.

    Args:
        input_type: Type of input (text, audio, image).
        session_id: Active session identifier.
        user_id: Optional user ID for consent lookup.
        text: Raw text input.
        audio: Audio bytes input.
        image: Image bytes input.
        image_type: Image subtype (e.g., document).
        response_mode: Desired response mode (text/voice).

    Returns:
        A response dictionary suitable for API output.
    """
    logger.info(
        "Interaction started",
        extra={"session_id": session_id, "input_type": input_type},
    )

    state = SessionState.load(session_id)
    consent = get_user_consent(user_id) if user_id else DEFAULT_DENY_CONSENT

    try:
        _validate_input_safety(audio=audio, image=image, consent=consent)

        normalized_text, context = route_input(
            input_type=input_type,
            text=text,
            audio=audio,
            image=image,
            image_type=image_type,
        )

        # adding agents CONTEXT AGENT (conversation continuity)
        # Inject summary + session memory ONCE here

        enriched_text = ContextAgent.build_input(
            user_input=normalized_text,
            input_type=input_type,
            user_id=user_id,
            session_id=session_id,
            session_state=state,
        )
        # ================== VOICE SHORT-CIRCUIT ==================
        if input_type == "audio":
            logger.info("Routing to voice chat pipeline")

            voice_response = await voice_chat_pipeline(
                audio_bytes=audio,
                user_id=user_id,
            )

            state.update_from_llm(voice_response)
            state.save()

            return voice_response
        # =========================================================

        check_output_safety(user_text=enriched_text)

        if detect_emergency(enriched_text):
            return _emergency_response()

        llm_result = _route_llm(
            input_type=input_type,
            normalized_text=enriched_text,
            image_type=image_type,
            state=state,
            context=context,
            user_id=user_id,
        )

        state.update_from_llm(llm_result)
        state.save()

        response = build_response(
            llm_result=llm_result,
            context=context,
            response_mode=response_mode,
            consent=consent,
        )

        logger.info("Interaction completed", extra={"session_id": session_id})
        response["session_id"] = state.session_id
        state.last_messages.append(
            {
                "role": "user",
                "content": normalized_text,
            }
        )

        state.last_messages.append(
            {
                "role": "assistant",
                "content": llm_result.get("response_text", ""),
            }
        )

        return response

    except SafetyViolation as exc:
        logger.warning("Safety violation", extra={"reason": str(exc)})
        return {"message": str(exc)}

    except Exception as exc:
        logger.exception("Unhandled interaction error")
        return {"message": "Something went wrong while processing your request."}


# ===================== HELPERS =====================


def _validate_input_safety(
    *,
    audio: bytes | None,
    image: bytes | None,
    consent: Dict[str, bool],
) -> None:
    """Validate input safety based on user consent."""
    if audio:
        check_input_safety("audio", consent)
    if image:
        check_input_safety("image", consent)


def _emergency_response() -> Dict[str, str]:
    """Return standardized emergency response."""
    return {
        "message": (
            "This sounds serious. Please seek immediate medical help "
            "or contact local emergency services."
        )
    }


def _route_llm(
    *,
    input_type: str,
    normalized_text: str,
    image_type: str | None,
    state: SessionState,
    context: Dict[str, Any],
    user_id: str | None,
) -> Dict[str, Any]:
    CONFIRMATIONS = {"yes", "yes.", "ok", "okay", "okay.", "sure"}

    if normalized_text.strip().lower() in CONFIRMATIONS:
        logger.info("User confirmed. Continuing self-care actions.")
        return analyze_health_text(
            text="Please give me some gentle self-care steps.",
            user_id=user_id,
            mode="self_care",
        )

    # ==========================================================
    # CONTEXT-AWARE HEALTH GATE (MODEL-CORRECT)
    # ==========================================================
    if (
        not _is_health_query(normalized_text)
        and not _asks_for_self_care(normalized_text)
        and not state.has_health_context
    ):
        return {
            "response_text": (
                "I'm here to help with health-related questions only. "
                "Please ask about symptoms, wellness, or self-care."
            ),
            "intent": "refusal",
            "severity": "low",
        }

    # ==========================================================
    # AUDIO
    # ==========================================================
    if input_type == "audio":
        return analyze_text(text=normalized_text, user_id=user_id)

    # ==========================================================
    # DOCUMENT OCR
    # ==========================================================
    if input_type == "image" and image_type == "document":
        return analyze_ocr_text(text=normalized_text, user_id=user_id)

    # ==========================================================
    # MEDICAL IMAGE
    # ==========================================================
    if input_type == "image":
        return {
            "intent": "image_analysis",
            "severity": "informational",
        }

    # ==========================================================
    # FOLLOW-UP AFTER IMAGE
    # ==========================================================
    if state.last_image_analysis:
        return analyze_health_text(
            text=normalized_text,
            image_context=state.last_image_analysis,
            user_id=user_id,
            mode="support",
        )
    # ==========================================================
    # EXPLICIT SELF-CARE OVERRIDE (ALWAYS WINS)
    # ==========================================================
    if _asks_for_self_care(normalized_text):
        logger.info("Explicit self-care detected. Forcing self_care mode.")
        return analyze_health_text(
            text=normalized_text,
            user_id=user_id,
            mode="self_care",
        )

    # ==========================================================
    # INTENT-DRIVEN HEALTH
    # ==========================================================
    intent = classify_intent_llm(normalized_text)
    # ==========================================================
    # CONTEXT-AWARE HEALTH GATE
    # ==========================================================

    if intent == "self_care":
        return analyze_health_text(
            text=normalized_text,
            user_id=user_id,
            mode="self_care",
        )

    if intent == "health_support":
        return analyze_health_text(
            text=normalized_text,
            user_id=user_id,
            mode="support",
        )

    # ==========================================================
    # DEFAULT (SAFE HEALTH CONTINUATION)
    # ==========================================================
    return analyze_health_text(
        text=normalized_text,
        user_id=user_id,
        mode="support",
    )


def _asks_for_self_care(text: str) -> bool:
    """Check if the user asks for self-care guidance."""
    text = text.lower()
    triggers = {
        "self care",
        "self-care",
        "tips",
        "suggest",
        "what can i do",
        "how can i",
        "how to feel better",
        "not feeling well",
        "feel better",
        "help me feel",
        "improve my health",
        "stay healthy",
        "healthy habits",
        "routine",
        "coping",
    }
    return any(t in text for t in triggers)


def _is_health_query(text: str) -> bool:
    """Check if the query relates to health symptoms."""

    health_triggers = {
        # symptoms
        "pain",
        "ache",
        "aches",
        "dizzy",
        "nausea",
        "fever",
        # anxiety & mental health
        "anxious",
        "anxiety",
        "uneasy",
        "worried",
        "overthinking",
        "panic",
        "fear",
        "stress",
        "tired",
        "fatigue",
        "low energy",
        "unwell",
        "feeling well",
        "burnout",
        "overwhelmed",
        # body awareness
        "body",
        "sensations",
        "symptom",
        "symptoms",
        # general health words
        "health",
        "wellbeing",
        "well-being",
    }
    return any(t in text.lower() for t in health_triggers)
