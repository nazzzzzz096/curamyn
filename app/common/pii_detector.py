"""
PII detection and redaction using Microsoft Presidio.
"""

from typing import List, Dict, Any
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Presidio engines (singleton pattern)
_analyzer = None
_anonymizer = None


def get_pii_analyzer() -> AnalyzerEngine:
    """Get or create PII analyzer instance."""
    global _analyzer

    if _analyzer is None:
        logger.info("Initializing Presidio PII analyzer")
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers()
        _analyzer = AnalyzerEngine(registry=registry)

    return _analyzer


def get_pii_anonymizer() -> AnonymizerEngine:
    """Get or create PII anonymizer instance."""
    global _anonymizer

    if _anonymizer is None:
        logger.info("Initializing Presidio PII anonymizer")
        _anonymizer = AnonymizerEngine()

    return _anonymizer


def detect_pii(text: str) -> List[Dict[str, Any]]:
    """
    Detect PII in text.

    Args:
        text: Text to analyze

    Returns:
        List of detected PII entities with type, location, and confidence
    """
    if not text or len(text) < 3:
        return []

    try:
        analyzer = get_pii_analyzer()

        results = analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "PERSON",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "LOCATION",
                "DATE_TIME",
                "US_SSN",
                "CREDIT_CARD",
                "IP_ADDRESS",
                "MEDICAL_LICENSE",
                "US_DRIVER_LICENSE",
            ],
            score_threshold=0.5,
        )

        detected = [
            {
                "type": result.entity_type,
                "start": result.start,
                "end": result.end,
                "score": result.score,
                "text": text[result.start : result.end],
            }
            for result in results
        ]

        if detected:
            logger.warning(
                f"PII detected in text: {len(detected)} entities found",
                extra={"pii_types": [d["type"] for d in detected]},
            )

        return detected

    except Exception as exc:
        logger.exception("PII detection failed")
        return []


def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
    """
    Redact PII from text.

    Args:
        text: Text containing PII
        replacement: Replacement text for PII

    Returns:
        Text with PII redacted
    """
    if not text or len(text) < 3:
        return text

    try:
        analyzer = get_pii_analyzer()
        anonymizer = get_pii_anonymizer()

        # Detect PII
        results = analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "PERSON",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "LOCATION",
                "DATE_TIME",
                "US_SSN",
                "CREDIT_CARD",
                "IP_ADDRESS",
                "MEDICAL_LICENSE",
                "US_DRIVER_LICENSE",
            ],
            score_threshold=0.5,
        )

        if not results:
            return text

        # Redact PII
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={
                "DEFAULT": OperatorConfig("replace", {"new_value": replacement})
            },
        )

        logger.info(
            f"PII redacted from text: {len(results)} entities",
            extra={"pii_types": [r.entity_type for r in results]},
        )

        return anonymized.text

    except Exception as exc:
        logger.exception("PII redaction failed")
        return text  # Return original text if redaction fails
