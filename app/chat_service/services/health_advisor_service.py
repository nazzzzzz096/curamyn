"""
Health advisor LLM service.

Provides supportive, non-diagnostic health guidance.
"""

import os
import time
import hashlib
from contextlib import nullcontext

import mlflow

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_NAME = "models/gemini-flash-latest"


# ==================================================
# SAFE LAZY LOADERS (CRITICAL FOR TESTS)
# ==================================================

def _load_gemini():
    """
    Safely load Gemini only in non-test environments.
    """
    if os.getenv("ENV") == "test":
        return None, None

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY missing, falling back")
            return None, None

        client = genai.Client(api_key=api_key)
        return client, GenerateContentConfig

    except Exception as exc:
        logger.warning("Gemini unavailable: %s", exc)
        return None, None


def _mlflow_context():
    """
    Disable MLflow completely during tests.
    Never breaks inference if MLflow is unavailable.
    """
    if os.getenv("ENV") == "test":
        return nullcontext()

    try:
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
        mlflow.set_experiment("curamyn_health_advisor")
        return mlflow.start_run(nested=True)
    except Exception:
        logger.warning("MLflow unavailable, running without tracking")
        return nullcontext()


def _safe_mlflow_call(func, *args, **kwargs):
    """
    Execute MLflow calls safely without affecting core logic.
    """
    try:
        func(*args, **kwargs)
    except Exception:
        pass


# ==================================================
# PUBLIC ENTRY POINT
# ==================================================

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
    client, GenerateContentConfig = _load_gemini()

    # ---------------- TEST / FALLBACK MODE ----------------
    if client is None:
        return {
            "intent": "health_advice",
            "severity": "informational",
            "response_text": (
                "I'm here to support you. "
                "If this concern continues, it may help to speak with a healthcare professional."
            ),
        }

    start_time = time.time()

    with _mlflow_context():
        _safe_mlflow_call(mlflow.set_tag, "service", "health_advisor_llm")
        if user_id:
            _safe_mlflow_call(mlflow.set_tag, "user_id", user_id)

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

        except Exception:
            logger.exception("Health advisor LLM failed")
            _safe_mlflow_call(mlflow.set_tag, "status", "failed")
            answer = ""

        if not answer:
            answer = (
                "I'm here to support you. "
                "If this concern continues, it may help to speak with a healthcare professional."
            )

        latency = time.time() - start_time

        _safe_mlflow_call(mlflow.log_param, "model", MODEL_NAME)
        _safe_mlflow_call(
            mlflow.log_param,
            "input_hash",
            hashlib.sha256(text.encode()).hexdigest(),
        )
        _safe_mlflow_call(mlflow.log_metric, "latency_sec", latency)
        _safe_mlflow_call(mlflow.set_tag, "status", "success")

        return {
            "intent": "health_advice",
            "severity": "informational",
            "response_text": answer,
        }


# ==================================================
# PROMPT BUILDER
# ==================================================

def _build_prompt(text: str, mode: str) -> str:
    """
    Build prompt based on advisory mode.
    """
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
