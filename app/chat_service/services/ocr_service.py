"""
OCR extraction service for medical documents.
"""

import io
from PIL import Image, ImageOps, ImageEnhance
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

        # Convert to RGB first (handles PNG transparency, etc.)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if image is too small (improves OCR accuracy)
        width, height = image.size
        if width < 1000:
            scale_factor = 1500 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(
                f"Upscaled image from {width}x{height} to {new_width}x{new_height}"
            )

        # Convert to grayscale
        image = ImageOps.grayscale(image)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

    except Exception as exc:
        logger.error("Failed to load/process image for OCR", exc_info=True)
        return ""

    # Try multiple PSM modes for better accuracy
    configs = [
        "--oem 3 --psm 3",  # Fully automatic page segmentation (default)
        "--oem 3 --psm 6 -c preserve_interword_spaces=1",
        "--oem 3 --psm 4",  # Assume single column of text
    ]

    raw_text = ""
    for config in configs:
        try:
            result = pytesseract.image_to_string(image, config=config)
            if result and len(result.strip()) > len(raw_text.strip()):
                raw_text = result
                logger.info(f"OCR successful with config: {config}")
        except Exception as exc:
            logger.warning(f"OCR failed with config {config}: {exc}")
            continue

    if not raw_text or len(raw_text.strip()) < 30:
        logger.warning("OCR output too short or empty")
        return ""

    logger.info(f"Raw OCR text length: {len(raw_text)}")
    logger.debug(f"Raw OCR preview: {raw_text[:200]}")

    cleaned_text = clean_ocr_text(raw_text)

    if not cleaned_text or len(cleaned_text) < 30:
        logger.warning("Cleaned OCR text is empty or too short")
        # Return raw text if cleaning removed too much
        if len(raw_text.strip()) >= 30:
            logger.info("Returning raw OCR text instead")
            return raw_text.strip()
        return ""

    logger.info(
        "OCR completed",
        extra={"final_length": len(cleaned_text)},
    )

    return cleaned_text
