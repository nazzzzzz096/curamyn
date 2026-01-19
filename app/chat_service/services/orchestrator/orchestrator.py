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
    # IMAGE (NON-OCR)
    # ==========================================================
    if input_type == "image":
        return {
            "intent": "image_analysis",
            "severity": "informational",
        }

    # ==========================================================
    # HEALTH TEXT (SINGLE PROMPT — ALWAYS)
    # ==========================================================
    return analyze_health_text(
        text=normalized_text,
        user_id=user_id,
    )
