"""
Main orchestration pipeline for handling user interactions.

This module coordinates:
- Input routing and normalization
- Consent and safety validation
- LLM invocation with context enrichment
- Session state management
- Response building and delivery

The orchestrator serves as the central hub for the chat service, handling the
complete lifecycle of user interactions from initial input processing through
final response generation, with integrated safety checks and memory management.
"""

from typing import Any, Dict
import time
from app.chat_service.services.orchestrator.input_router import route_input
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.services.orchestrator.response_builder import build_response
from app.chat_service.services.voice_pipeline_service import voice_chat_pipeline

from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.health_advisor_service import analyze_health_text
from app.chat_service.services.ocr_llm_service import analyze_ocr_text
from app.chat_service.services.educational_llm_service import explain_medical_terms
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
    """Orchestrates a single user interaction lifecycle."""

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

        # ✅ Store document text + track when it was uploaded
        if input_type == "image" and image_type == "document" and normalized_text:
            state.last_document_text = normalized_text
            state.document_uploaded_at = time.time()
            state.document_upload_message_index = len(
                state.all_messages
            )  # ✅ Track position
            logger.info("Stored document text with message index")

        # ✅ Store image analysis + track when it was uploaded
        if context.get("image_analysis"):
            state.last_image_analysis = context["image_analysis"]
            state.last_image_type = image_type
            state.image_upload_message_index = len(
                state.all_messages
            )  # ✅ Track position
            state.save()
            logger.info(
                "Stored image analysis with message index",
                extra={"image_type": image_type},
            )

        # Build enriched context
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
                session_state=state,
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

        # ✅ Use new add_message method
        state.add_message("user", normalized_text)
        state.add_message("assistant", llm_result.get("response_text", ""))

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


def _is_asking_about_medical_terms(text: str, document_text: str = "") -> bool:
    """
    Detect if user is asking about medical terminology or document content.

    This function should return True for:
    - "What is hemoglobin?"
    - "What is the normal range for hemoglobin?"
    - "Why is my TSH high?"
    - "Is my WBC count okay?"
    - "Should I be worried about RBC?"
    - "Explain my platelet count"

    Args:
        text: User's question
        document_text: The uploaded document text (to check if terms are in document)

    Returns:
        True if question is about medical terms/document content
    """
    text_lower = text.lower()

    # ===== PATTERN 1: Direct Questions =====
    question_patterns = [
        "what is",
        "what does",
        "what are",
        "what's",
        "whats",
        "explain",
        "define",
        "meaning of",
        "what do you mean by",
        "tell me about",
        "can you explain",
    ]

    # ===== PATTERN 2: Concern/Interpretation Questions =====
    concern_patterns = [
        "is my",
        "should i be worried",
        "is this normal",
        "is this okay",
        "is this bad",
        "is this good",
        "why is my",
        "what does it mean",
        "does this mean",
        "is it concerning",
        "is it serious",
    ]

    # ===== PATTERN 3: Range/Value Questions =====
    range_patterns = [
        "normal range",
        "reference range",
        "should be",
        "supposed to be",
        "ideal level",
        "healthy level",
        "target range",
    ]

    # ===== Medical Terms (from document context) =====
    medical_terms = [
        # Blood count terms
        "rbc",
        "wbc",
        "hemoglobin",
        "haemoglobin",
        "hb",
        "platelet",
        "mcv",
        "mch",
        "mchc",
        "rdw",
        "neutrophil",
        "lymphocyte",
        "monocyte",
        "eosinophil",
        "basophil",
        "hematocrit",
        "haematocrit",
        "differential",
        # Thyroid terms
        "tsh",
        "t3",
        "t4",
        "free t3",
        "free t4",
        "thyroid",
        # Metabolic terms
        "glucose",
        "blood sugar",
        "hba1c",
        "a1c",
        "cholesterol",
        "hdl",
        "ldl",
        "triglyceride",
        "creatinine",
        "urea",
        "bun",
        # Liver terms
        "alt",
        "ast",
        "alp",
        "bilirubin",
        "ggt",
        "sgot",
        "sgpt",
        "liver enzyme",
        # Minerals/Electrolytes
        "sodium",
        "potassium",
        "calcium",
        "magnesium",
        "iron",
        "ferritin",
        "vitamin",
        # General terms
        "count",
        "level",
        "result",
        "value",
        "test",
        "cells",
        "mg/dl",
        "g/dl",
        "mmol/l",
        "µl",
        "ul",
    ]

    # ===== DETECTION LOGIC =====

    # Check if any question pattern exists
    has_question_pattern = any(pattern in text_lower for pattern in question_patterns)
    has_concern_pattern = any(pattern in text_lower for pattern in concern_patterns)
    has_range_pattern = any(pattern in text_lower for pattern in range_patterns)

    # Check if medical terms are mentioned
    has_medical_term = any(term in text_lower for term in medical_terms)

    # ✅ MATCH 1: Direct questions about medical terms
    # Example: "What is hemoglobin?"
    if has_question_pattern and has_medical_term:
        return True

    # ✅ MATCH 2: Concern/interpretation questions
    # Example: "Is my hemoglobin okay?" or "Why is my TSH high?"
    if has_concern_pattern and has_medical_term:
        return True

    # ✅ MATCH 3: Range/value questions
    # Example: "What is the normal range for hemoglobin?"
    if has_range_pattern and has_medical_term:
        return True

    # ✅ MATCH 4: Check if question references document content
    # Example: "What about the result in my report?"
    document_references = [
        "my report",
        "my test",
        "my results",
        "in my",
        "from my",
        "this report",
        "the report",
        "the test",
        "these results",
    ]

    if any(ref in text_lower for ref in document_references):
        return True

    #  MATCH 5: Very short questions that likely refer to document context
    # Example: After seeing a report, user just asks "Normal range?"
    words = text_lower.split()
    if len(words) <= 4 and has_medical_term:
        return True

    return False


def _is_topic_change(text: str) -> bool:
    """
    Detect if user is changing topics away from document discussion.

    Args:
        text: User's message

    Returns:
        True if user is clearly changing topics
    """
    text_lower = text.lower()

    # Phrases indicating topic change
    topic_change_indicators = [
        "i want to talk about",
        "can we discuss",
        "let's talk about",
        "i have a question about",
        "i'm feeling",
        "i feel",
        "i've been",
        "help me with",
        "i need help",
        "can you help me",
        "advice",
        "stressed",
        "anxious",
        "worried",
        "tired",
        "sleep",
        "exercise",
        "diet",
        "nutrition",
    ]

    return any(indicator in text_lower for indicator in topic_change_indicators)


def _route_llm(
    *,
    input_type: str,
    normalized_text: str,
    image_type: str | None,
    state: SessionState,
    context: Dict[str, Any],
    user_id: str | None,
) -> Dict[str, Any]:
    """
    Routes normalized input to the appropriate LLM service based on input type.

    Determines which LLM service to invoke based on input modality and context:
    - Audio inputs are analyzed with general text analysis
    - Document OCR extracts medical insights from scanned documents
    - Images are flagged for non-OCR analysis
    - Text inputs use smart routing with topic detection and document context management

    Args:
        input_type: Type of input (text, audio, image).
        normalized_text: Processed and cleaned input text.
        image_type: Subtype of image input (e.g., 'document').
        state: Current session state with memory and context.
        context: Additional contextual information from the session.
        user_id: Optional user ID for consent and preference lookup.

    Returns:
        A dictionary containing LLM analysis results with keys like 'intent',
        'severity', and service-specific response data.
    """
    # ==========================================================
    # AUDIO
    # ==========================================================
    if input_type == "audio":
        return analyze_text(text=normalized_text, user_id=user_id)

    # ==========================================================
    # DOCUMENT OCR
    # ==========================================================
    if input_type == "image" and image_type == "document":
        state.document_uploaded_at = time.time()
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
    # TEXT INPUT - SMART ROUTING
    # ==========================================================

    if input_type == "text":

        # CHECK 1: Topic change
        if _is_topic_change(normalized_text):
            logger.info("Topic change detected - clearing document context")
            state.clear_document_context()
            session_context = state.get_current_context()
            return analyze_health_text(
                text=normalized_text,
                user_id=user_id,
                session_context=session_context,
            )

        # CHECK 2: Document context staleness
        if state.last_document_text and state.is_document_context_stale(
            max_age_seconds=600
        ):
            logger.info("Document context expired (>10 minutes) - clearing")
            state.clear_document_context()

        # ✅ NEW CHECK 3: Full document summary request
        if state.last_document_text:
            wants_full_summary = any(
                phrase in normalized_text.lower()
                for phrase in [
                    "what was in",
                    "what did the report",
                    "summarize my report",
                    "summary of",
                    "overview of",
                    "main findings",
                ]
            )

            if wants_full_summary:
                logger.info("✓ Routing to health advisor WITH document context")
                session_context = state.get_current_context()

                # ✅ Pass document context to health advisor
                return analyze_health_text(
                    text=normalized_text,
                    user_id=user_id,
                    session_context=session_context,
                    # Document context is already in enriched_text via ContextAgent
                )

            # CHECK 4: Specific medical term explanation
            is_medical_question = _is_asking_about_medical_terms(
                normalized_text, state.last_document_text
            )

            if is_medical_question:
                logger.info("✓ Routing to educational LLM")
                return explain_medical_terms(
                    question=normalized_text,
                    document_text=state.last_document_text,
                    user_id=user_id,
                )

        # DEFAULT: Health advisor
        logger.info("Routing to health advisor (general conversation)")
        session_context = state.get_current_context()
        return analyze_health_text(
            text=normalized_text,
            user_id=user_id,
            session_context=session_context,
        )
