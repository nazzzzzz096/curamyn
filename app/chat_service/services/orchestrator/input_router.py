"""
Input routing logic.

Routes multimodal user input to the correct preprocessing pipeline.
"""

from typing import Tuple, Dict, Any

from app.chat_service.services.whisper_service import transcribe
from app.chat_service.services.ocr_service import extract_text
from app.chat_service.services.cnn_service import predict_risk
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def route_input(
    *,
    input_type: str,
    text: str | None,
    audio: bytes | None,
    image: bytes | None,
    image_type: str | None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Normalize raw user input into text and context.

    Supported routes:
    - audio  → speech-to-text
    - image  → OCR and optional CNN analysis
    - text   → direct pass-through

    Args:
        input_type (str): Input modality.
        text (str | None): Text input.
        audio (bytes | None): Audio bytes.
        image (bytes | None): Image bytes.
        image_type (str | None): Image category hint.

    Returns:
        Tuple[str, Dict[str, Any]]: Normalized text and context.

    Raises:
        ValueError: If required input data is missing or unsupported.
    """
    logger.info(
        "Routing input",
        extra={"input_type": input_type},
    )

    context: Dict[str, Any] = {}

    if input_type == "audio":
        if not audio:
            raise ValueError("Audio bytes missing")

        normalized_text = transcribe(audio)

    elif input_type == "image":
        if not image or not image_type:
            raise ValueError("Image or image_type missing")

        normalized_text = extract_text(image) or "[IMAGE_INPUT]"

        if image_type in {"xray", "skin"}:
            context["image_analysis"] = predict_risk(
                image_type=image_type,
                image_bytes=image,
            )

    elif input_type == "text":
        if not text:
            raise ValueError("Text input missing")

        normalized_text = text.strip()

    else:
        raise ValueError(f"Unsupported input_type: {input_type}")

    logger.debug(
        "Input normalized",
        extra={"preview": normalized_text[:80]},
    )

    return normalized_text, context
