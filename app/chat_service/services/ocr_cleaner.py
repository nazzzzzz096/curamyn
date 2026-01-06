"""
OCR text cleaner.

Removes personal identifiers and OCR noise
while preserving medical content.
"""

import re
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

PII_PATTERNS = [
    r"patient\s*name.*",
    r"patient\s*id.*",
    r"age\s*[:=].*",
    r"gender\s*[:=].*",
    r"sample\s*collected.*",
    r"report\s*generated.*",
    r"date\s*[:=].*",
    r"referral.*",
    r"doctor.*",
]

_COMPILED_PII = [re.compile(p) for p in PII_PATTERNS]


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

        if not stripped or len(stripped) < 4:
            continue

        if any(p.search(lower) for p in _COMPILED_PII):
            continue

        if re.fullmatch(r"[a-z\s]{1,5}", lower):
            continue

        cleaned_lines.append(stripped)

    cleaned_text = "\n".join(cleaned_lines)

    logger.info(
        "OCR cleaning completed",
        extra={"cleaned_length": len(cleaned_text)},
    )

    return cleaned_text
