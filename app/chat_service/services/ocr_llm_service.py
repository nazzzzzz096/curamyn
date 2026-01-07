"""
OCR document understanding LLM service.
Safe for CI and tests.
"""

import os
import time
from types import SimpleNamespace

import mlflow
from dotenv import load_dotenv

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)
load_dotenv()

MODEL_NAME = "models/gemini-flash-latest"

# --------------------------------------------------
# Test-safe dummy client (for patching & imports)
# --------------------------------------------------
class _NullGeminiClient:
    """Null object for Gemini client (safe fallback)."""

    class models:
        @staticmethod
        def generate_content(*args, **kwargs):
            return None

def _load_gemini():
    if os.getenv("ENV") == "test":
        return _NullGeminiClient(), None



# ==================================================
# Lazy Gemini loader
# ==================================================
def _load_gemini():
    """
    Lazily load Gemini only outside test environments.
    """
    if os.getenv("ENV") == "test":
        return None, None

    try:
        from google import generativeai as genai
        from google.generativeai.types import GenerationConfig

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None, None

        genai.configure(api_key=api_key)
        return genai, GenerationConfig

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

    if not text or len(text) < 80:
        return _fallback("The uploaded image could not be read clearly.")

    if not _is_medical_document(text):
        return _fallback(
            "This document does not appear to be a medical laboratory report."
        )

    global client

    # Respect patched client in tests
    if client is not None:
        active_client = client
        GenerationConfig = None
    else:
        active_client, GenerationConfig = _load_gemini()

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
                generation_config=GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=400,
                ) if GenerationConfig else None,
            )
            output = _extract_llm_text(response)

        except Exception:
            logger.exception("OCR LLM call failed")
            output = ""

        if not output or len(output.split(".")) < 3:
            logger.warning("OCR LLM output too short — fallback applied")
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
    keywords = [
        "blood", "cbc", "hemoglobin", "platelet",
        "wbc", "rbc", "esr", "lab report", "test result",
    ]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)


def _build_prompt(text: str) -> str:
    return f"""
You are a medical document summarization system.

RULES (STRICT):
- NO diagnosis
- NO medical advice
- NO interpretation
- Professional tone only
- Multi-sentence output required

Document Text:
{text}
"""


def _extract_llm_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


