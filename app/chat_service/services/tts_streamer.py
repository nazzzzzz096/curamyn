from pathlib import Path
import io
import wave
from typing import Optional

from piper import PiperVoice

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# ======================================================
# CONFIG
# ======================================================

MODEL_PATH = Path("/app/models/en_US-amy-low.onnx")
SAMPLE_RATE = 22050
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM

# Cached voice instance
_voice: Optional[PiperVoice] = None


# ======================================================
# INTERNAL HELPERS
# ======================================================


def _load_voice() -> PiperVoice:
    """
    Lazily load and cache the Piper voice model.
    """
    global _voice

    if _voice is not None:
        return _voice

    if not MODEL_PATH.exists():
        logger.error(
            "Piper model file not found",
            extra={"path": str(MODEL_PATH)},
        )
        raise FileNotFoundError(f"Piper model not found at {MODEL_PATH}")

    try:
        logger.info(
            "Loading Piper model",
            extra={"path": str(MODEL_PATH)},
        )

        _voice = PiperVoice.load(str(MODEL_PATH))

        logger.info("Piper model loaded successfully")
        return _voice

    except Exception:
        logger.exception("Failed to load Piper model")
        raise


def pcm_to_wav_bytes(
    pcm_bytes: bytes,
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
    sample_width: int = SAMPLE_WIDTH,
) -> bytes:
    """
    Wrap raw PCM audio bytes into a WAV container.

    Args:
        pcm_bytes: Raw 16-bit PCM audio
        sample_rate: Sampling rate (Hz)
        channels: Audio channels
        sample_width: Bytes per sample (2 = int16)

    Returns:
        WAV-encoded audio bytes
    """
    try:
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)

        return buffer.getvalue()

    except Exception:
        logger.exception("Failed to convert PCM to WAV")
        raise


# ======================================================
# PUBLIC API
# ======================================================


def synthesize_tts(text: str) -> bytes:
    """
    Convert text to speech using Piper.

    Returns:
        WAV-encoded audio bytes compatible with browsers.
    """
    if not text or not text.strip():
        logger.debug("Empty text received for TTS request")
        return b""

    try:
        voice = _load_voice()
        pcm_audio = b""

        for chunk in voice.synthesize(text):
            pcm_audio += chunk.audio_int16_bytes

        logger.debug(
            "TTS PCM generated",
            extra={"pcm_bytes": len(pcm_audio)},
        )

        wav_audio = pcm_to_wav_bytes(pcm_audio)

        logger.debug(
            "TTS WAV generated",
            extra={"wav_bytes": len(wav_audio)},
        )

        return wav_audio

    except Exception:
        logger.exception(
            "TTS synthesis failed",
            extra={"text_preview": text[:50]},
        )
        return b""
