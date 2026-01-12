from app.chat_service.services.whisper_service import transcribe
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def finalize_spoken_text(text: str, severity: str) -> str:
    text = text.strip()

    if text and text[-1] in ".!?":
        return text

    endings = {
        "low": ["That makes sense."],
        "moderate": ["You're doing the best you can."],
        "high": ["You don’t have to go through this alone."],
    }

    return f"{text}. {endings.get(severity, ['I hear you.'])[0]}"


def voice_chat_pipeline(
    audio_bytes: bytes,
    user_id: str | None = None,
) -> dict:
    """
    Voice pipeline (TEXT ONLY).
    Audio is streamed separately via WebSocket.
    """
    logger.info("Voice pipeline started")

    try:
        # 1️⃣ STT
        user_text = transcribe(audio_bytes)

        if not user_text:
            return {
                "message": "Sorry, I couldn't hear you clearly. Please try again.",
                "severity": "low",
            }

        # 2️⃣ LLM
        llm_result = analyze_text(
            text=user_text,
            user_id=user_id,
        )

        response_text = llm_result.get("response_text", "").strip()
        severity = llm_result.get("severity", "low")

        # 3️⃣ Final spoken text
        spoken_text = finalize_spoken_text(response_text, severity)

        logger.info("Voice pipeline completed")

        #  NO AUDIO HERE
        return {
            "message": spoken_text,
            "severity": severity,
        }

    except Exception:
        logger.exception("Voice pipeline failed")
        raise
