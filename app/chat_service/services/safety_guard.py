"""
Safety guard module.

Enforces consent, blocks medical diagnosis/dosage requests,
and detects emergency language.
"""

from typing import Dict

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# --- Forbidden health patterns (deterministic) ---
DIAGNOSIS_KEYWORDS = [
    "diagnose", "diagnosis", "is this cancer",
    "do i have", "what disease",
]

DOSAGE_KEYWORDS = [
    "dosage", "dose", "how much medicine",
    "how many mg", "how many tablets",
]

EMERGENCY_KEYWORDS = [
    "suicide", "kill myself", "end my life",
    "can't breathe", "severe chest pain",
    "heart attack", "collapse", "fainted",
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
        raise SafetyViolation(
            "Voice processing is disabled by user consent."
        )

    if input_type == "image" and not consent.get("image"):
        logger.warning("Image input blocked due to consent")
        raise SafetyViolation(
            "Image processing is disabled by user consent."
        )

    if input_type == "document" and not consent.get("document"):
        logger.warning("Document input blocked due to consent")
        raise SafetyViolation(
            "Document processing is disabled by user consent."
        )


# ---------------- OUTPUT SAFETY ---------------- #

def check_output_safety(*, user_text: str) -> None:
    """
    Block forbidden medical requests.
    """
    if not user_text:
        return

    lowered = user_text.lower()

    for word in DIAGNOSIS_KEYWORDS:
        if word in lowered:
            logger.warning("Diagnosis request blocked")
            raise SafetyViolation(
                "Medical diagnosis requests are not supported."
            )

    for word in DOSAGE_KEYWORDS:
        if word in lowered:
            logger.warning("Medication dosage request blocked")
            raise SafetyViolation(
                "Medication dosage advice is not allowed."
            )


def detect_emergency(user_text: str) -> bool:
    """
    Detect emergency or crisis language.
    """
    if not user_text:
        return False

    lowered = user_text.lower()

    detected = any(
        phrase in lowered
        for phrase in EMERGENCY_KEYWORDS
    )

    if detected:
        logger.warning("Emergency language detected")

    return detected
