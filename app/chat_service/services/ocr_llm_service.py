"""
OCR document understanding LLM service.
Safe for CI and tests.
"""

import os
import time
import re
from types import SimpleNamespace

import mlflow
from dotenv import load_dotenv

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)
load_dotenv()
client = None
MODEL_NAME = "models/gemini-flash-latest"
import random
from google.genai.errors import ServerError


def _call_gemini_with_retry(
    *,
    client,
    model: str,
    contents: str,
    config,
    retries: int = 4,
    base_delay: float = 1.0,
):
    """Call Gemini's `models.generate_content` with retry and exponential backoff.

    This helper invokes `client.models.generate_content` and implements a simple
    retry loop for transient server-side errors (for example HTTP 503 /
    overloaded model responses). Retries use exponential backoff with a small
    random jitter to reduce contention.

    Args:
        client: An initialized Gemini client providing ``models.generate_content``.
        model (str): Model identifier to request (for example ``models/gemini-flash-latest``).
        contents (str): Prompt or input contents to send to the model.
        config: Configuration object passed through to ``generate_content`` (e.g.
            a ``GenerateContentConfig`` instance) or ``None``.
        retries (int): Maximum number of attempts (including the first). Default is 4.
        base_delay (float): Base delay in seconds used for exponential backoff.

    Returns:
        The raw response returned by ``client.models.generate_content``.

    Raises:
        ServerError: Re-raises a ``ServerError`` when the error is not recognized as
            a transient overload, or when the retry budget is exhausted.
        Exception: Any other exception raised by the client is propagated.

    Notes:
        The function treats ServerError messages that contain ``"503"`` or
        ``"UNAVAILABLE"`` as transient and will retry them. Each retry sleeps for
        ``base_delay * (2 ** attempt) + jitter`` where jitter is drawn from
        ``uniform(0, 0.5)`` seconds.
    """
    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        except ServerError as exc:
            # 503 / overloaded model
            if "503" in str(exc) or "UNAVAILABLE" in str(exc):
                if attempt == retries - 1:
                    raise

                sleep_time = base_delay * (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Gemini overloaded, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "sleep_sec": round(sleep_time, 2),
                    },
                )
                time.sleep(sleep_time)
            else:
                raise


# ==================================================
# Clean markdown formatting
# ==================================================
def _clean_markdown(text: str) -> str:
    """
    Remove markdown formatting and clean up LLM output.

    Args:
        text: Raw LLM output with markdown formatting

    Returns:
        Clean, readable text
    """
    if not text:
        return text

    # Remove markdown headers (##, ###)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers (**text**, *text*)
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)

    # Remove table separators (|----|---|)
    text = re.sub(r"\|[\s\-:]+\|", "", text)

    # Clean up pipe characters used in tables
    text = re.sub(r"\s*\|\s*", " | ", text)

    # Remove multiple consecutive blank lines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


# ==================================================
#  Gemini loader
# ==================================================
_GEMINI_CLIENT = None
_GEMINI_CONFIG = None


def _load_gemini():
    global _GEMINI_CLIENT, _GEMINI_CONFIG
    """Load and cache a Gemini client and content config type.

    This function attempts to import and construct a Gemini client using the
    environment variable ``CURAMYN_GEMINI_API_KEY``. It caches the created
    client and the ``GenerateContentConfig`` type in module-level variables
    so subsequent calls return the same objects.

    Behavior:
        - If ``CURAMYN_ENV`` is set to ``test``, returns ``(None, None)`` to
          avoid external network calls during tests.
        - If no API key is set or an import/initialization error occurs,
          the function logs a warning and returns ``(None, None)``.

    Returns:
        tuple: ``(client, GenerateContentConfig)`` on success, or ``(None, None)``
        when Gemini is unavailable or not configured.

    Side effects:
        Sets the module-level ``_GEMINI_CLIENT`` and ``_GEMINI_CONFIG`` on
        successful initialization.
    """

    if _GEMINI_CLIENT is not None:
        return _GEMINI_CLIENT, _GEMINI_CONFIG

    if os.getenv("CURAMYN_ENV") == "test":
        return None, None

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("CURAMYN_GEMINI_API_KEY")
        if not api_key:
            return None, None

        _GEMINI_CLIENT = genai.Client(api_key=api_key)
        _GEMINI_CONFIG = GenerateContentConfig
        return _GEMINI_CLIENT, _GEMINI_CONFIG

    except Exception as exc:
        logger.warning("Gemini OCR unavailable: %s", exc)
        return None, None


# ==================================================
# Public API
# ==================================================
def analyze_ocr_text(*, text: str, user_id: str | None = None) -> dict:
    """
    Summarize a medical laboratory document extracted via OCR.
    """
    logger.info(
        "OCR LLM service called",
        extra={"text_length": len(text) if text else 0},
    )

    # Log preview of extracted text for debugging
    if text:
        logger.info(f"OCR text preview (first 200 chars): {text[:200]}")

    # Reduced minimum length threshold
    if not text or len(text) < 30:
        logger.warning("OCR text too short")
        return _fallback("The uploaded image could not be read clearly.")

    # More lenient medical document detection
    if not _is_medical_document(text):
        logger.warning("Text doesn't appear to be medical document")
        logger.debug(f"Full text: {text}")
        return _fallback(
            "This document does not appear to be a medical laboratory report."
        )

    active_client, GenerationConfig = (
        (client, None) if client is not None else _load_gemini()
    )

    if active_client is None:
        return _fallback_text_response()

    start = time.time()

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "ocr_document_llm")
        if user_id:
            mlflow_safe(mlflow.set_tag, "user_id", user_id)

        prompt = _build_prompt(text)

        try:
            response = _call_gemini_with_retry(
                client=active_client,
                model=MODEL_NAME,
                contents=prompt,
                config=(
                    GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                    )
                    if GenerationConfig
                    else None
                ),
            )

            output = _extract_llm_text(response)

            # Clean markdown formatting
            output = _clean_markdown(output)

            logger.info(f"LLM response length: {len(output)}")
            logger.debug(f"LLM response preview: {output[:200]}")

        except Exception as exc:
            logger.exception(
                "OCR LLM call failed",
                extra={"error_type": exc.__class__.__name__},
            )
            output = ""

        # Just return whatever LLM gives us
        if not output or len(output) < 50:
            logger.warning("OCR LLM returned insufficient output")
            output = _fallback_text()

        latency = time.time() - start
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)

        return {
            "intent": "document_understanding",
            "severity": "informational",
            "response_text": output,
        }


# ==================================================
# Helpers
# ==================================================
def _fallback(message: str) -> dict:
    """
    Create a fallback response dictionary with a custom message.

    Wraps a custom message in the standard response format when document
    analysis cannot be performed or when pre-validation checks fail.

    Args:
        message: Custom message to include in the response

    Returns:
        dict: Response with keys:
            - intent: Set to "document_understanding"
            - severity: Set to "informational"
            - response_text: The provided message
    """
    return {
        "intent": "document_understanding",
        "severity": "informational",
        "response_text": message,
    }


def _fallback_text_response() -> dict:
    """
    Create a fallback response with the default fallback message.

    Combines fallback functionality with the standard fallback text message.
    Used when the Gemini client is unavailable or when LLM processing fails.

    Returns:
        dict: Fallback response with standard format and default message
    """
    return _fallback(_fallback_text())


def _fallback_text() -> str:
    """
    Return the default fallback message for document analysis failures.

    Provides a user-friendly message when document understanding cannot
    be performed due to extraction quality or processing issues.

    Returns:
        str: Default fallback message explaining the limitation
    """
    return (
        "This appears to be a medical laboratory document. "
        "However, the extracted text does not provide enough structure "
        "to confidently summarize specific sections. "
        "Please upload a clearer image."
    )


def _is_medical_document(text: str) -> bool:
    """Check if text appears to be from a medical document."""
    keywords = [
        # Blood tests
        "blood",
        "cbc",
        "hemoglobin",
        "platelet",
        "wbc",
        "rbc",
        "esr",
        "hematology",
        "haematology",
        # Document structure
        "lab report",
        "laboratory",
        "test result",
        "clinical",
        "pathology",
        "diagnostic",
        # Common medical terms
        "patient",
        "sample",
        "specimen",
        "reference range",
        "normal range",
        # Medical measurements
        "g/dl",
        "mg/dl",
        "cells/ul",
        "count",
        "differential",
        # Other tests
        "glucose",
        "creatinine",
        "cholesterol",
        "liver",
        "kidney",
        "thyroid",
    ]
    text_lower = text.lower()

    # Require at least 2 medical keywords for confidence
    matches = sum(1 for k in keywords if k in text_lower)
    logger.info(f"Medical keyword matches: {matches}")

    return matches >= 2


def _build_prompt(text: str) -> str:
    """Build prompt for LLM to summarize medical document."""
    return f"""
You are a medical document extraction assistant.

Extract and organize the key information from this medical lab report.

DOCUMENT TEXT:
{text}

IMPORTANT FORMATTING RULES:
- DO NOT use markdown formatting (no **, ##, ***, etc.)
- DO NOT use tables with pipes and dashes
- Use simple, plain text formatting
- Use line breaks and indentation for structure
- Use simple dashes (-) for bullet points if needed

Provide a clear, structured summary with:
1. Report type (e.g., Haematology Report, CBC)
2. All test parameters with values and reference ranges
3. Any remarks or clinical notes

Format it clearly and simply. DO NOT interpret or diagnose - just present the data.
"""


def _extract_llm_text(response) -> str:
    """Extract text from Gemini response."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""
