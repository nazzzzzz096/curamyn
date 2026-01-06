from app.chat_service.services.whisper_service import transcribe
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.tts_service import text_to_speech
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def finalize_spoken_text(text: str, severity: str) -> str:
    """
    Normalize spoken text endings for empathy.
    """
    text = text.strip()

    if text and text[-1] in ".!?":
        return text

    endings = {
        "low": [
            "That makes sense.",
            "Yeah, I get that.",
            "Sounds about right.",
        ],
        "moderate": [
            "Take it one step at a time.",
            "You're doing the best you can.",
            "That's a lot to carry.",
        ],
        "high": [
            "You don’t have to go through this alone.",
            "I’m really glad you reached out.",
            "You deserve support.",
        ],
    }

    extra = endings.get(severity, ["I hear you."])[0]
    return f"{text}. {extra}"


def voice_chat_pipeline(
    audio_bytes: bytes,
    user_id: str | None = None,
) -> bytes:
    """
    End-to-end voice interaction pipeline.
    """
    logger.info("Voice pipeline started")

    try:
        user_text = transcribe(audio_bytes)

        llm_result = analyze_text(
            text=user_text,
            user_id=user_id,
        )

        if llm_result.get("severity") == "high":
            logger.warning("High-severity voice interaction detected")

        spoken = finalize_spoken_text(
            llm_result.get("response_text", ""),
            llm_result.get("severity", "low"),
        )

        audio = text_to_speech(spoken)

        logger.info("Voice pipeline completed")
        return audio

    except Exception:
        logger.exception("Voice pipeline failed")
        raise

    