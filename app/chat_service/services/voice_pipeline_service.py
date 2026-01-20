# app/chat_service/services/voice_pipeline_service.py

from app.chat_service.services.whisper_service import transcribe
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.tts_streamer import synthesize_tts
from app.chat_service.utils.logger import get_logger
import base64

logger = get_logger(__name__)


def normalized_response_text(text: str, severity: str) -> str:
    text = text.strip()

    if text and text[-1] in ".!?":
        return text

    endings = {
        "low": "That makes sense.",
        "moderate": "You're doing the best you can.",
        "high": "You don’t have to go through this alone.",
    }

    return f"{text}. {endings.get(severity, 'I hear you.')}"


async def voice_chat_pipeline(
    audio_bytes: bytes,
    user_id: str | None = None,
) -> dict:
    logger.info("Voice pipeline started")

    # 1. Speech-to-Text
    user_text = transcribe(audio_bytes)

    if not user_text:
        return {
            "message": "Sorry, I couldn't hear you clearly. Please try again.",
            "tts_failed": True,
        }

    # 2. LLM
    llm_result = analyze_text(
        text=user_text,
        user_id=user_id,
    )

    response_text = llm_result.get("response_text", "")
    severity = llm_result.get("severity", "low")

    spoken_text = normalized_response_text(response_text, severity)

    # 3. Text-to-Speech
    try:
        audio_bytes_out = synthesize_tts(spoken_text)

        audio_base64 = base64.b64encode(audio_bytes_out).decode("utf-8")

        logger.info("Voice pipeline completed successfully")

        return {
            "message": spoken_text,
            "audio_base64": audio_base64,
            "severity": severity,
            "tts_failed": False,
        }

    except Exception:
        logger.warning("TTS failed, falling back to text only")

        return {
            "message": spoken_text,
            "audio_base64": None,
            "severity": severity,
            "tts_failed": True,
        }
