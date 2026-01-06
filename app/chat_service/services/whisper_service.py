"""
Speech-to-text service using Whisper.
"""

import os
import tempfile
import whisper

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

model = whisper.load_model("base")


def transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes into text.
    """
    logger.info("Whisper STT started")

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = model.transcribe(tmp_path)

        text = result.get("text", "").strip()
        logger.info("Whisper STT completed")
        return text

    except Exception:
        logger.exception("Whisper transcription failed")
        return ""

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
