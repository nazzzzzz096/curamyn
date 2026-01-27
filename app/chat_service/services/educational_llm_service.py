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
    - Answer questions about terms, values, or ranges in the document
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

        prompt = f"""You are a medical terminology educator helping someone understand their lab report.

USER'S DOCUMENT (for reference):
{document_text}

USER'S QUESTION:
{question}

STRICT RULES:
1. Answer ANY question related to the document content
2. This includes:
   - What medical terms mean (e.g., "What is hemoglobin?")
   - What normal/reference ranges mean (e.g., "What is the normal range for hemoglobin?")
   - What units mean (e.g., "What does g/dL mean?")
   - What test categories mean (e.g., "What is a CBC?")
   - General education about tests in the document

3. Do NOT:
   - Diagnose conditions
   - Interpret if the USER'S specific values are normal/abnormal
   - Provide medical advice
   - Recommend treatments

4. Acceptable to say:
   ✅ "Hemoglobin is a protein in red blood cells that carries oxygen. The normal range for adults is typically 12-16 g/dL for women and 14-18 g/dL for men."
   ✅ "TSH stands for Thyroid Stimulating Hormone. Normal ranges are usually 0.4-4.0 mIU/L."
   ✅ "WBC count measures white blood cells which fight infection."

5. NOT acceptable:
   ❌ "Your hemoglobin of 10.8 is low, you might have anemia"
   ❌ "This result is abnormal"
   ❌ "You should take iron supplements"

If the question is about a term NOT in the document, say:
"That term doesn't appear in your uploaded document. I can only explain terms from your report."

If the user asks for diagnosis or interpretation of THEIR values, say:
"I can explain what the term means and what normal ranges typically are, but I cannot interpret your specific results or diagnose conditions. Please discuss your results with your healthcare provider."

Provide a clear, educational explanation in 2-4 sentences."""

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
