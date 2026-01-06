"""
Health advisor LLM service.

Provides supportive, non-diagnostic health guidance.
"""

import time
import hashlib
import os

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
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-flash-latest"

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
mlflow.set_experiment("curamyn_health_advisor")


def analyze_health_text(
    *,
    text: str,
    user_id: str | None = None,
    mode: str = "support",
) -> dict:
    """
    Health advisor LLM.

    Modes:
    - support: emotional reassurance
    - self_care: practical self-care tips

    Returns non-diagnostic, safe responses only.
    """
    start = time.time()

    with mlflow.start_run(nested=True):
        mlflow.set_tag("service", "health_advisor_llm")
        if user_id:
            mlflow.set_tag("user_id", user_id)

        prompt = _build_prompt(text, mode)

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=300,
                ),
            )
            answer = response.text.strip() if response.text else ""

        except Exception as exc:
            logger.exception("Health advisor LLM failed")
            mlflow.set_tag("status", "failed")
            answer = ""

        if not answer:
            answer = (
                "I'm here to support you. "
                "If this concern continues, it may help to speak with a healthcare professional."
            )

        mlflow.log_param("model", MODEL_NAME)
        mlflow.log_param(
            "input_hash",
            hashlib.sha256(text.encode()).hexdigest(),
        )
        mlflow.log_metric("latency_sec", time.time() - start)
        mlflow.set_tag("status", "success")

        return {
            "intent": "health_advice",
            "severity": "informational",
            "response_text": answer,
        }


def _build_prompt(text: str, mode: str) -> str:
    """Build prompt based on advisory mode."""
    if mode == "self_care":
        return f"""
You are a health information assistant.

Rules:
- Give practical self-care tips
- No diagnosis
- No medicine names
- Gentle language

User:
{text}

Response:
- Start with 1 empathetic sentence
- Then list 3–5 self-care tips
"""

    return f"""
You are a supportive health listener.

Rules:
- Emotional reassurance
- No diagnosis
- Gentle tone

User:
{text}
"""

