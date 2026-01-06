"""
OCR extraction service for medical documents.
"""

import io
from PIL import Image, ImageOps
import pytesseract

from app.chat_service.utils.logger import get_logger
from app.chat_service.services.ocr_cleaner import clean_ocr_text

logger = get_logger(__name__)


def extract_text(image_bytes: bytes) -> str:
    """
    Perform OCR on document image and return cleaned text.

    Args:
        image_bytes (bytes): Raw image bytes.

    Returns:
        str: Cleaned OCR text or empty string.
    """
    logger.info("OCR started")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.grayscale(image)
    except Exception as exc:
        logger.error("Failed to load image for OCR")
        return ""

    raw_text = pytesseract.image_to_string(
        image,
        config="--oem 3 --psm 6",
    )

    if not raw_text or len(raw_text.strip()) < 30:
        logger.warning("OCR output too short or empty")
        return ""

    cleaned_text = clean_ocr_text(raw_text)

    if not cleaned_text or len(cleaned_text) < 30:
        logger.warning("Cleaned OCR text is empty or too short")
        return ""

    logger.info(
        "OCR completed",
        extra={"final_length": len(cleaned_text)},
    )

    return cleaned_text
