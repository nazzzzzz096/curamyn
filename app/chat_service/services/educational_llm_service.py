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
    Explain medical terms OR summarize document from user's uploaded file.
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

        #  Detect if user wants full summary vs. term explanation
        wants_summary = any(
            phrase in question.lower()
            for phrase in [
                "what was in",
                "summarize",
                "summary of",
                "what did",
                "what does it say",
                "overview",
                "main findings",
                "key results",
            ]
        )

        if wants_summary:
            mlflow_safe(mlflow.set_tag, "mode", "document_summary")
            prompt = f"""You are a medical document summarizer.

USER'S DOCUMENT:
{document_text}

USER'S QUESTION:
{question}

TASK:
Provide a clear, structured summary of the document's main content.

RULES:
1. List the report type (e.g., "Complete Blood Count", "Haematology Report")
2. Highlight key test parameters and their values
3. Note any remarks or observations mentioned
4. DO NOT diagnose or interpret if values are normal/abnormal
5. DO NOT provide medical advice
6. Present information factually and clearly

Format your response as:

Report Type: [name]

Key Findings:
- [Parameter 1]: [Value] (Reference: [range])
- [Parameter 2]: [Value] (Reference: [range])
...

Remarks: [if any]

Provide the summary now:"""

        else:
            mlflow_safe(mlflow.set_tag, "mode", "term_explanation")
            prompt = f"""You are a medical terminology educator helping someone understand their lab report.

USER'S DOCUMENT (for reference):
{document_text}

USER'S QUESTION:
{question}

STRICT RULES:
1. Answer ANY question related to the document content
2. This includes:
   - What medical terms mean (e.g., "What is hemoglobin?")
   - What normal/reference ranges mean
   - What units mean (e.g., "What does g/dL mean?")
   - What test categories mean

3. Do NOT:
   - Diagnose conditions
   - Interpret if USER'S specific values are normal/abnormal
   - Provide medical advice
   - Recommend treatments

Provide a clear, educational explanation in 2-4 sentences."""

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=(
                    GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=(
                            800 if wants_summary else 500
                        ),  # More tokens for summaries
                    )
                    if GenerateContentConfig
                    else None
                ),
            )

            output = _extract_text(response)

        except Exception:
            logger.exception("Educational LLM call failed")
            output = "I'm having trouble processing that right now. Please try again."

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
