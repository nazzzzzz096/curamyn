"""
Educational LLM service for explaining medical terms.

ONLY activated when user asks about terms from their uploaded document.
Does NOT diagnose - only explains terminology.
"""

import os
import time

import mlflow
from dotenv import load_dotenv

from app.chat_service.utils.logger import get_logger
from app.common.mlflow_control import mlflow_context, mlflow_safe

logger = get_logger(__name__)
load_dotenv()

MODEL_NAME = "models/gemini-flash-latest"


def _load_gemini():
    """Load Gemini client safely."""
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
        logger.warning("Gemini unavailable: %s", exc)
        return None, None


def explain_medical_terms(
    *,
    question: str,
    document_text: str,
    user_id: str | None = None,
) -> dict:
    """
    Explain medical terms from the user's uploaded document.

    STRICT RULES:
    - Only explain terms that appear in the document
    - Do NOT diagnose
    - Do NOT say if results are normal/abnormal
    - Educational purpose only

    Args:
        question: User's question about terms
        document_text: The extracted document text
        user_id: Optional user identifier

    Returns:
        dict with intent, severity, and response_text
    """
    logger.info("Educational mode activated")

    client, GenerateContentConfig = _load_gemini()

    if client is None:
        return {
            "intent": "educational",
            "severity": "informational",
            "response_text": "I can help explain medical terms, but the system is currently unavailable.",
        }

    start_time = time.time()

    with mlflow_context():
        mlflow_safe(mlflow.set_tag, "service", "educational_llm")
        mlflow_safe(mlflow.set_tag, "mode", "term_explanation")

        if user_id:
            mlflow_safe(mlflow.set_tag, "user_id", user_id)

        prompt = f"""You are a medical terminology educator.

USER'S DOCUMENT (for reference only):
{document_text}

USER'S QUESTION:
{question}

STRICT RULES:
1. ONLY explain terms that appear in the user's document above
2. Do NOT diagnose or interpret the results
3. Do NOT say if values are normal, abnormal, high, or low
4. Do NOT give medical advice
5. ONLY provide educational information about what the term means

If the user asks about a term NOT in their document, say:
"I can only explain terms from your uploaded document. That term doesn't appear in your report."

If the user asks for diagnosis or interpretation, say:
"I can explain what the terms mean, but I cannot interpret your results or provide a diagnosis. Please consult your healthcare provider."

Provide a clear, simple explanation in 2-3 sentences."""

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=(
                    GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=500,
                    )
                    if GenerateContentConfig
                    else None
                ),
            )

            output = _extract_text(response)

        except Exception:
            logger.exception("Educational LLM call failed")
            output = "I'm having trouble explaining that right now. Please try again."

        latency = time.time() - start_time
        mlflow_safe(mlflow.log_metric, "latency_sec", latency)

        return {
            "intent": "educational",
            "severity": "informational",
            "response_text": output
            or "I can help explain medical terms from your document. What would you like to know?",
        }


def _extract_text(response) -> str:
    """Extract text from Gemini response."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""
