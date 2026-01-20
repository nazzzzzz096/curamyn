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
# Lazy Gemini loader
# ==================================================
def _load_gemini():
    """
    Lazily load Gemini only outside test environments.
    """
    if os.getenv("CURAMYN_ENV") == "test":
        return None, None

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("CURAMYN_GEMINI_API_KEY")
        if not api_key:
            return None, None

        return genai.Client(api_key=api_key), GenerateContentConfig

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
            response = active_client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=(
                    GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2048,  # Increased for full reports
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

        except Exception:
            logger.exception("OCR LLM call failed")
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
    return {
        "intent": "document_understanding",
        "severity": "informational",
        "response_text": message,
    }


def _fallback_text_response() -> dict:
    return _fallback(_fallback_text())


def _fallback_text() -> str:
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
