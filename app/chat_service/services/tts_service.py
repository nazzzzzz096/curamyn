"""
Text-to-Speech service using edge-tts.
Browser-safe, async-safe, reliable.
"""

import os
from tempfile import NamedTemporaryFile

import edge_tts
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


async def text_to_speech(text: str) -> bytes:
    """
    Convert text to speech using Edge Neural voices.

    Returns:
        bytes: MP3 audio bytes
    """
    logger.info("TTS started (edge-tts)")

    tmp_path = None

    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice="en-IN-NeerjaNeural",
        )

        with NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)

        with open(tmp_path, "rb") as f:
            audio = f.read()

        logger.info("TTS completed (edge-tts)")
        return audio

    except Exception:
        logger.exception("TTS failed (edge-tts)")
        raise

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
