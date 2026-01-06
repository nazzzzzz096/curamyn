"""
OCR document understanding LLM service.
"""

import os
import time
import mlflow
from google import genai
from google.genai.types import GenerateContentConfig

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# --------------------------------------------------
# Environment validation
# --------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not configured")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-flash-latest"

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
mlflow.set_experiment("curamyn_llm_services")


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

    start = time.time()

    with mlflow.start_run(nested=True):
        mlflow.set_tag("service", "ocr_document_llm")

        prompt = _build_prompt(text)

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=400,
                ),
            )
            output = _extract_llm_text(response)

        except Exception:
            logger.exception("OCR LLM call failed")
            output = ""

        if not output or len(output.split(".")) < 3:
            logger.warning("OCR LLM output too short — fallback applied")
            output = _fallback_text()

        mlflow.log_metric("latency_sec", time.time() - start)

        return {
            "intent": "document_understanding",
            "severity": "informational",
            "response_text": output,
        }


# ---------------- HELPERS ---------------- #

def _fallback(message: str) -> dict:
    return {
        "intent": "document_understanding",
        "severity": "informational",
        "response_text": message,
    }


def _fallback_text() -> str:
    return (
        "This appears to be a medical laboratory document.\n"
        "However, the extracted text does not provide enough structure "
        "to confidently summarize specific sections.\n"
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
- NOT diagnosis
- NO advice
- NO normal/abnormal interpretation
- NOT user-facing tone
- Multi-sentence output required

Document Text:
{text}
"""


def _extract_llm_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""
