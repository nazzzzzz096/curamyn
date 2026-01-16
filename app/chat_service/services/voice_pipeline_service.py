from app.chat_service.services.whisper_service import transcribe
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.utils.logger import get_logger
import base64
from app.chat_service.services.tts_streamer import stream_tts

logger = get_logger(__name__)


def normalized_response_text(text: str, severity: str) -> str:
    text = text.strip()

    if text and text[-1] in ".!?":
        return text

    endings = {
        "low": ["That makes sense."],
        "moderate": ["You're doing the best you can."],
        "high": ["You don’t have to go through this alone."],
    }

    return f"{text}. {endings.get(severity, ['I hear you.'])[0]}"


async def voice_chat_pipeline(
    audio_bytes: bytes,
    user_id: str | None = None,
) -> dict:
    logger.info("Voice pipeline started")

    # 1 STT
    user_text = transcribe(audio_bytes)

    if not user_text:
        return {
            "message": "Sorry, I couldn't hear you clearly. Please try again.",
        }

    #  LLM
    llm_result = analyze_text(
        text=user_text,
        user_id=user_id,
    )

    response_text = llm_result.get("response_text", "").strip()
    severity = llm_result.get("severity", "low")

    spoken_text = normalized_response_text(response_text, severity)
    if not user_text:
        spoken_text = "Sorry, I could not hear you clearly. Please try again."

    #  TTS (THIS WAS MISSING)
    audio_bytes_out = b""
    async for chunk in stream_tts(spoken_text):
        audio_bytes_out += chunk

    audio_base64 = base64.b64encode(audio_bytes_out).decode()

    logger.info("Voice pipeline completed")

    return {
        "message": spoken_text,
        "audio_base64": audio_base64,
        "severity": severity,
    }
