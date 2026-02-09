"""
Speech-to-text service using Whisper (FALLBACK ONLY).
"""

import os
import subprocess
import tempfile
import time

from app.observability.metrics import (
    STT_REQUEST_LATENCY,
    STT_REQUESTS_TOTAL,
    STT_ERRORS_TOTAL,
)
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

ENGINE = "whisper"
_model = None


def _load_whisper():
    """Lazy-load Whisper model (only if fallback is enabled)."""
    global _model
    if _model is None:
        import whisper

        logger.info("Loading Whisper model (fallback)")
        _model = whisper.load_model("base")
    return _model


def transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes into text using Whisper fallback.
    """
    if os.getenv("CURAMYN_ENV") == "test":
        return "hello"

    if not os.getenv("ENABLE_WHISPER_FALLBACK"):
        raise RuntimeError("Whisper fallback disabled")

    start_time = time.time()
    webm_path = None
    wav_path = None

    logger.info("Whisper STT started")

    try:
        model = _load_whisper()

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            webm_path = f.name

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

        result = model.transcribe(wav_path)
        text = result.get("text", "").strip()

        if not text:
            STT_ERRORS_TOTAL.labels(
                engine=ENGINE,
                error_type="audio_empty",
            ).inc()

            STT_REQUESTS_TOTAL.labels(
                engine=ENGINE,
                status="failure",
            ).inc()

            return ""

        STT_REQUESTS_TOTAL.labels(
            engine=ENGINE,
            status="success",
        ).inc()

        return text

    except subprocess.CalledProcessError:
        STT_ERRORS_TOTAL.labels(
            engine=ENGINE,
            error_type="ffmpeg_failed",
        ).inc()

        STT_REQUESTS_TOTAL.labels(
            engine=ENGINE,
            status="failure",
        ).inc()

        logger.exception("FFmpeg conversion failed")
        return ""

    except Exception:
        STT_ERRORS_TOTAL.labels(
            engine=ENGINE,
            error_type="whisper_failed",
        ).inc()

        STT_REQUESTS_TOTAL.labels(
            engine=ENGINE,
            status="failure",
        ).inc()

        logger.exception("Whisper transcription failed")
        return ""

    finally:
        STT_REQUEST_LATENCY.labels(
            engine=ENGINE,
        ).observe(time.time() - start_time)

        for path in (webm_path, wav_path):
            if path and os.path.exists(path):
                os.remove(path)
