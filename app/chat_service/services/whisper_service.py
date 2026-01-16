"""
Speech-to-text service using Whisper.
"""

import os
import subprocess
import tempfile
import whisper

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

if os.getenv("CURAMYN_ENV") == "test":
    model = None
else:
    model = whisper.load_model("base")


def transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes into text.
    """
    if os.getenv("CURAMYN_ENV") == "test":
        return "hello"
    logger.info("Whisper STT started")

    webm_path = None
    wav_path = None

    try:
        #  Save incoming WEBM audio
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            webm_path = f.name

        #  Convert to WAV (16kHz mono PCM)
        wav_path = webm_path.replace(".webm", ".wav")

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                webm_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                wav_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        #  Transcribe clean WAV
        result = model.transcribe(wav_path)

        text = result.get("text", "").strip()
        logger.info("Whisper STT completed")

        return text

    except Exception:
        logger.exception("Whisper transcription failed")
        return ""

    finally:
        for path in (webm_path, wav_path):
            if path and os.path.exists(path):
                os.remove(path)
