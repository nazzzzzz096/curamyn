"""
Main orchestration pipeline.

Coordinates multimodal input processing, safety checks,
LLM routing, session state tracking, and response generation.

IMPORTANT:
- This module NEVER persists memory.
- Session memory lives only in RAM.
- Memory storage & cleanup are handled on session END (logout).
"""

from typing import Dict, Any

from app.chat_service.services.orchestrator.input_router import route_input
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.services.orchestrator.response_builder import build_response

# LLM services
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.health_advisor_service import analyze_health_text
from app.chat_service.services.ocr_llm_service import analyze_ocr_text
from app.chat_service.services.intent_classifier import classify_intent_llm


# Safety & consent
from app.chat_service.services.safety_guard import (
    check_input_safety,
    check_output_safety,
    detect_emergency,
    SafetyViolation,
)

from app.consent_service.service import get_user_consent
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_DENY_CONSENT = {
    "voice": False,
    "image": False,
    "document": False,
    "memory": False,
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
    Execute a single AI interaction cycle.

    Responsibilities:
    - Consent validation
    - Input preprocessing
    - Safety checks
    - LLM routing
    - Session state updates (RAM ONLY)
    - Response construction

    This function NEVER:
    - Stores memory
    - Calls summarization
    - Writes to database
    """

    logger.info(
        "Interaction started",
        extra={
            "session_id": session_id,
            "input_type": input_type,
            "user_id": user_id,
        },
    )

    # Load or create in-memory session
    state = SessionState.load(session_id)
    consent = get_user_consent(user_id) if user_id else DEFAULT_DENY_CONSENT

    # ---------------- INPUT + SAFETY ----------------
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
    logger.warning(
    f"ROUTING DEBUG | "
    f"text='{normalized_text}' | "
    f"asks_for_self_care={_asks_for_self_care(normalized_text)} | "
    f"is_health_query={_is_health_query(normalized_text)}"
)

    try:
        # AUDIO → GENERAL / VOICE CHAT
        if input_type == "audio":
            llm_result = analyze_text(
                text=normalized_text,
                user_id=user_id,
            )

        # DOCUMENT IMAGE → OCR → SUMMARY
        elif input_type == "image" and image_type == "document":
            llm_result = analyze_ocr_text(
                text=normalized_text,
                user_id=user_id,
            )
            state.last_document_text = normalized_text

        # MEDICAL IMAGE → CNN ONLY (NO LLM RESPONSE)
        elif input_type == "image":
            image_analysis = context.get("image_analysis")
            if image_analysis:
                state.last_image_analysis = image_analysis

            llm_result = {
                "intent": "image_analysis",
                "severity": "informational",
            }

        # FOLLOW-UP AFTER IMAGE ANALYSIS
        elif input_type == "text" and state.last_image_analysis:
            llm_result = analyze_health_text(
                text=(
                    "Context: The user previously uploaded a medical report.\n"
                    f"Report analysis:\n{state.last_image_analysis}\n\n"
                    f"User follow-up question:\n{normalized_text}\n\n"
                    "Respond with continuity. Do NOT ask what report again."
        ),
        user_id=user_id,
    )

            state.update_from_llm(llm_result)
            state.save()

            return build_response(
            llm_result=llm_result,
            context=context,
            response_mode=response_mode,
            consent=consent,
    )


        # ---------------- TEXT ROUTING (FIXED ORDER) ----------------

        #  SELF-CARE FIRST

        if _asks_for_self_care(normalized_text):
            llm_result = analyze_health_text(
                text=normalized_text,
                user_id=user_id,
                mode="self_care",
            )

        # 2 HEALTH SUPPORT
        elif _is_health_query(normalized_text):
            llm_result = analyze_health_text(
                text=normalized_text,
                user_id=user_id,
                mode="support",
            )

        # Ambiguous → LLM intent classifier
        else:
            intent = classify_intent_llm(normalized_text)
            if intent == "self_care":
                llm_result = analyze_health_text(
            text=normalized_text,
            user_id=user_id,
            mode="self_care",
                )
            elif intent == "health_support":
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

    except Exception:
        logger.exception(
            "LLM processing failed",
            extra={"session_id": session_id},
        )
        return {"message": "Something went wrong while processing your request."}

    # ---------------- SESSION STATE UPDATE ----------------
    try:
        state.update_from_llm(llm_result)
        state.save()
    except Exception as exc:
        logger.error(
            "Failed to update session state",
            extra={"session_id": session_id, "error": str(exc)},
        )

    logger.info(
        "Interaction completed",
        extra={"session_id": session_id},
    )

    # ---------------- RESPONSE ----------------
    return build_response(
        llm_result=llm_result,
        context=context,
        response_mode=response_mode,
        consent=consent,
    )


# ---------------- PRIVATE HELPERS ----------------
def _asks_for_self_care(text: str) -> bool:
    """
    Detect self-care or wellness improvement queries.
    """
    lowered = text.lower()

    triggers = [
        "self care",
        "self-care",
        "improve my health",
        "improve health",
        "feel healthier",
        "be healthier",
        "how can i improve",
        "how to improve",
        "stay healthy",
        "healthy habits",
        "what should i do to",
        "what can i do to",
        "help me improve",
    ]

    return any(trigger in lowered for trigger in triggers)



def _is_health_query(text: str) -> bool:
    """
    Detect symptom-based or distress-based health queries.
    """
    lowered = text.lower()

    symptoms = [
        "pain",
        "ache",
        "dizzy",
        "dizziness",
        "nausea",
        "vomit",
        "headache",
        "fever",
        "weak",
        "anxious",
        "anxiety",
        "panic",
        "stress",
        "worried",
        "can't sleep",
        "not feeling well",
    ]

    return any(symptom in lowered for symptom in symptoms)

