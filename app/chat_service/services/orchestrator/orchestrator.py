"""
Main orchestration pipeline.

Coordinates multimodal input processing, safety checks,
LLM routing, state management, and response generation.
"""

from typing import Dict, Any

from app.chat_service.services.orchestrator.input_router import route_input
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.services.orchestrator.response_builder import build_response

# LLM services
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.health_advisor_service import analyze_health_text
from app.chat_service.services.ocr_llm_service import analyze_ocr_text

# Safety & consent
from app.chat_service.services.safety_guard import (
    check_input_safety,
    check_output_safety,
    detect_emergency,
    SafetyViolation,
)
from app.chat_service.repositories.session_repositories import (
    store_session_summary,
)
from app.chat_service.services.session_summary_service import (
    generate_session_summary,
)

from app.consent_service.service import get_user_consent

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_DENY_CONSENT = {
    "voice": False,
    "image": False,
    "document": False,
}


def run_interaction(
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
    Execute a full AI interaction cycle.

    Handles:
    - Consent checks
    - Input preprocessing
    - Safety screening
    - LLM routing
    - Session state tracking
    - Response construction

    Returns:
        Dict[str, Any]: Final response payload.
    """
    logger.info(
        "Interaction started",
        extra={
            "session_id": session_id,
            "input_type": input_type,
            "user_id": user_id,
        },
    )

    state = SessionState.load(session_id)
    consent = get_user_consent(user_id) if user_id else DEFAULT_DENY_CONSENT

    try:
        if audio:
            check_input_safety("audio", consent)
        if image:
            check_input_safety("image", consent)

        normalized_text, context = route_input(
            input_type=input_type,
            text=text,
            audio=audio,
            image=image,
            image_type=image_type,
        )

        check_output_safety(user_text=normalized_text)

    except SafetyViolation as exc:
        logger.warning(
            "Safety violation",
            extra={"session_id": session_id, "reason": str(exc)},
        )
        return {"message": str(exc)}

    # ---------------- EMERGENCY OVERRIDE ----------------
    if detect_emergency(user_text=normalized_text):
        logger.warning(
            "Emergency detected",
            extra={"session_id": session_id},
        )
        return {
            "message": (
                "This sounds serious. Please seek immediate medical help "
                "or contact local emergency services."
            )
        }

    # ---------------- LLM ROUTING ----------------

    try:
        if input_type == "audio":
            llm_result = analyze_text(
                text=normalized_text,
                user_id=user_id,
            )

        elif input_type == "image" and image_type == "document":
            llm_result = analyze_ocr_text(
                text=normalized_text,
                user_id=user_id,
            )
            state.last_document_text = normalized_text

        elif input_type == "image":
            image_analysis = context.get("image_analysis")
            if image_analysis:
                state.last_image_analysis = image_analysis

            llm_result = {
                "intent": "image_analysis",
                "severity": "informational",
            }

        elif input_type == "text" and state.last_image_analysis:
            llm_result = analyze_health_text(
                text=(
                    "The user previously saw a medical image result:\n"
                    f"{state.last_image_analysis}\n\n"
                    f"User question:\n{normalized_text}\n\n"
                    "Explain calmly. Provide self-care tips if helpful. "
                    "Do NOT diagnose."
                ),
                user_id=user_id,
            )
        # ---- GENERAL CHAT FIRST ----
        elif input_type == "text" and not _is_health_query(normalized_text):
            llm_result = analyze_text(text=normalized_text, user_id=user_id)


        elif _asks_for_self_care(normalized_text):
            llm_result = analyze_health_text(
                text=normalized_text,
                user_id=user_id,
                mode="self_care",
            )

        elif _is_health_query(normalized_text):
            llm_result = analyze_health_text(
                text=normalized_text,
                user_id=user_id,
                mode="support",
            )

        else:
            llm_result = analyze_text(
                text=normalized_text,
                user_id=user_id,
            )

    except Exception as exc:
        logger.exception(
            "LLM processing failed",
            extra={"session_id": session_id},
        )
        return {"message": "Something went wrong while processing your request."}

    # ---------------- STATE UPDATE ----------------
    try:
        state.update_from_llm(llm_result)
        state.save()
    except Exception as exc:
        logger.error(
            "Failed to persist session state",
            extra={"session_id": session_id, "error": str(exc)},
        )

    logger.info(
        "Interaction completed",
        extra={"session_id": session_id},
    )
    # ---------------- MEMORY STORAGE ---------------- #
    if consent.get("memory") and user_id:
        try:
            summary = generate_session_summary(state.__dict__)
            store_session_summary(
            session_id=session_id,
            user_id=user_id,
            summary=summary,
        )
            logger.info("Session memory stored | session=%s", session_id)
        except Exception as exc:
            logger.warning(
            "Memory storage failed | session=%s | error=%s",
            session_id,
            exc,
        )

    return build_response(
        llm_result=llm_result,
        context=context,
        response_mode=response_mode,
        consent=consent,
    )


# ---------------- PRIVATE HELPERS ----------------

def _asks_for_self_care(text: str) -> bool:
    """Detect self-care related user queries."""
    triggers = [
        "self care",
        "self-care",
        "what can i do",
        "what should i do",
        "give me tips",
        "care tips",
        "how to manage",
    ]
    text = text.lower()
    return any(t in text for t in triggers)


def _is_health_query(text: str) -> bool:
    """Detect symptom-related health queries."""
    symptoms = [
        "dizziness",
        "nausea",
        "vomiting",
        "headache",
        "fever",
        "pain",
        "weak",
        "stomach",
        "cough",
        "cold",
    ]
    text = text.lower()
    return any(s in text for s in symptoms)
