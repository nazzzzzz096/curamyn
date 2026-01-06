"""
Text-to-Speech service (offline, privacy-safe).
"""

import os
from tempfile import NamedTemporaryFile
import pyttsx3

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def _init_engine() -> pyttsx3.Engine:
    """Initialize and configure TTS engine."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 145)
    engine.setProperty("volume", 0.9)

    voices = engine.getProperty("voices")
    for voice in voices:
        if "female" in voice.name.lower() or "zira" in voice.name.lower():
            engine.setProperty("voice", voice.id)
            break

    return engine


def _soften_for_voice(text: str) -> str:
    """
    Make text sound more natural when spoken.
    """
    return (
        text.replace("...", ",")
        .replace(".", ",")
        .replace("!", ".")
        .replace("  ", " ")
        .strip()
    )


def text_to_speech(text: str) -> bytes:
    """
    Convert text to empathetic spoken audio.

    Returns:
        bytes: WAV audio bytes
    """
    logger.info("TTS started")

    spoken_text = _soften_for_voice(text)
    tmp_path = None

    engine = _init_engine()

    try:
        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(spoken_text, tmp_path)
        engine.runAndWait()

        with open(tmp_path, "rb") as audio_file:
            audio = audio_file.read()

        logger.info("TTS completed")
        return audio

    except Exception:
        logger.exception("TTS failed")
        raise

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

