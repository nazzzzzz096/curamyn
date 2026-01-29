"""
Safety guard with scope checking - refuses non-health queries
"""

from typing import Dict

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# --- Forbidden health patterns ---
DIAGNOSIS_KEYWORDS = [
    "diagnose",
    "diagnosis",
    "is this cancer",
    "do i have",
    "what disease",
]

DOSAGE_KEYWORDS = [
    "dosage",
    "dose",
    "how much medicine",
    "how many mg",
    "how many tablets",
]

EMERGENCY_KEYWORDS = [
    "suicide",
    "kill myself",
    "end my life",
    "can't breathe",
    "severe chest pain",
    "heart attack",
    "collapse",
    "fainted",
]

# ✅ NEW: Out-of-scope (general knowledge) patterns
GENERAL_KNOWLEDGE_PATTERNS = [
    "who is",
    "who was",
    "when was",
    "where is",
    "what is the capital",
    "tell me about",
    "history of",
    "biography",
    "famous person",
    "historical figure",
    "politician",
    "celebrity",
    "actor",
    "singer",
    "sports",
    "weather in",
    "temperature in",
    "news about",
    "latest news",
]

# Health-related keywords (to avoid false positives)
HEALTH_KEYWORDS = [
    "symptom",
    "health",
    "medical",
    "doctor",
    "hospital",
    "disease",
    "condition",
    "treatment",
    "pain",
    "ache",
    "feel",
    "feeling",
    "sick",
    "ill",
    "medication",
    "therapy",
    "wellness",
    "mental health",
    "anxiety",
    "depression",
    "stress",
    "sleep",
    "tired",
    "fatigue",
    "diet",
    "nutrition",
    "exercise",
    "weight",
    "blood",
    "pressure",
    "sugar",
    "cholesterol",
    "heart",
    "lung",
    "kidney",
    "liver",
]


class SafetyViolation(Exception):
    """Raised when a safety rule is violated."""


# ---------------- INPUT SAFETY ---------------- #


def check_input_safety(
    input_type: str,
    consent: Dict[str, bool],
) -> None:
    """
    Block execution if user has not given consent.
    """
    if input_type == "audio" and not consent.get("voice"):
        logger.warning("Voice input blocked due to consent")
        raise SafetyViolation("Voice processing is disabled by user consent.")

    if input_type == "image" and not consent.get("image"):
        logger.warning("Image input blocked due to consent")
        raise SafetyViolation("Image processing is disabled by user consent.")

    if input_type == "document" and not consent.get("document"):
        logger.warning("Document input blocked due to consent")
        raise SafetyViolation("Document processing is disabled by user consent.")


# ---------------- OUTPUT SAFETY ---------------- #


def check_output_safety(*, user_text: str) -> None:
    """
    Block forbidden medical requests and out-of-scope general knowledge questions.
    """
    if not user_text:
        return

    lowered = user_text.lower()

    # ✅ NEW: Check for out-of-scope general knowledge questions
    is_health_related = any(keyword in lowered for keyword in HEALTH_KEYWORDS)

    if not is_health_related:
        # Check if it's a general knowledge question
        for pattern in GENERAL_KNOWLEDGE_PATTERNS:
            if pattern in lowered:
                logger.warning(f"General knowledge question detected: {pattern}")
                raise SafetyViolation(
                    "I'm here to help with health and wellness topics. "
                    "For general information, please try a search engine or encyclopedia."
                )

    # Existing checks
    for word in DIAGNOSIS_KEYWORDS:
        if word in lowered:
            logger.warning("Diagnosis request blocked")
            raise SafetyViolation("Medical diagnosis requests are not supported.")

    for word in DOSAGE_KEYWORDS:
        if word in lowered:
            logger.warning("Medication dosage request blocked")
            raise SafetyViolation("Medication dosage advice is not allowed.")


def detect_emergency(user_text: str) -> bool:
    """
    Detect emergency or crisis language.
    """
    if not user_text:
        return False

    lowered = user_text.lower()

    detected = any(phrase in lowered for phrase in EMERGENCY_KEYWORDS)

    if detected:
        logger.warning("Emergency language detected")

    return detected
