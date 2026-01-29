"""
OCR text cleaner.

Removes personal identifiers and OCR noise
while preserving medical content.
"""

import re
from app.chat_service.utils.logger import get_logger
from app.common.pii_detector import redact_pii

logger = get_logger(__name__)

# More specific PII patterns that won't match important medical terms
PII_PATTERNS = [
    r"^patient\s*name\s*[:=]",
    r"^patient\s*id\s*[:=]",
    r"^name\s*[:=]",
    r"^id\s*[:=]",
    r"^uhid\s*[:=]",
    r"^mr\s*no\s*[:=]",
]

_COMPILED_PII = [re.compile(p, re.IGNORECASE) for p in PII_PATTERNS]


def clean_ocr_text(text: str) -> str:
    """
    Remove personal identifiers and OCR garbage.

    Args:
        text (str): Raw OCR output.

    Returns:
        str: Privacy-safe cleaned text.
    """
    if not text:
        return ""

    cleaned_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        # Skip empty lines
        if not stripped:
            continue

        # Skip lines that are too short (likely OCR noise)
        # BUT allow short lines if they contain numbers or medical abbreviations
        if len(stripped) < 3:
            continue

        # Skip lines with only 1-2 characters that are just letters
        if len(stripped) <= 2 and stripped.isalpha():
            continue

        # Check for PII patterns (only at start of line)
        is_pii = any(p.match(lower) for p in _COMPILED_PII)
        if is_pii:
            logger.debug(f"Removed PII line: {stripped[:50]}")
            continue

        # Keep lines that contain medical keywords (even if short)
        medical_keywords = [
            "hemoglobin",
            "hb",
            "wbc",
            "rbc",
            "platelet",
            "glucose",
            "creatinine",
            "urea",
            "sodium",
            "potassium",
            "count",
            "test",
            "result",
            "value",
            "range",
            "reference",
            "unit",
            "cbc",
            "report",
            "clinical",
            "remarks",
            "normal",
            "high",
            "low",
            "neutrophil",
            "lymphocyte",
            "monocyte",
            "eosinophil",
            "mcv",
            "mch",
            "mchc",
            "g/dl",
            "mg/dl",
            "mmol/l",
            "cells/ul",
        ]

        has_medical_keyword = any(keyword in lower for keyword in medical_keywords)
        has_numbers = any(char.isdigit() for char in stripped)

        # Keep line if it has medical keywords, numbers, or is substantial
        if has_medical_keyword or has_numbers or len(stripped) >= 4:
            cleaned_lines.append(stripped)

    cleaned_text = "\n".join(cleaned_lines)

    cleaned_text = redact_pii(cleaned_text, replacement="[REDACTED]")

    logger.info(
        "OCR cleaning completed with PII redaction",
        extra={
            "original_lines": len(text.splitlines()),
            "cleaned_lines": len(cleaned_lines),
            "cleaned_length": len(cleaned_text),
        },
    )

    return cleaned_text
