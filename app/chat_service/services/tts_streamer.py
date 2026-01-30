"""
Optimized Piper TTS with caching and proper WAV output.

 Converts raw PCM to proper WAV format
 Proper error message propagation
 Text truncation preserves word boundaries
"""

import io
import subprocess
import wave
from typing import Optional

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

#  TTS CACHE for instant responses
_TTS_CACHE: dict[str, bytes] = {}


def init_tts_cache():
    """Pre-generate common TTS responses at startup."""
    global _TTS_CACHE

    common_phrases = {
        "hello": "Hello! How can I help you today?",
        "error": "Sorry, I didn't catch that clearly. Could you try again?",
        "goodbye": "Take care! I'm here whenever you need me.",
        "thinking": "Let me think about that for a moment.",
    }

    logger.info("🔄 Pre-generating TTS cache...")

    for key, text in common_phrases.items():
        try:
            _TTS_CACHE[key] = _synthesize_piper(text)
            logger.debug(f"Cached '{key}': {len(_TTS_CACHE[key])} bytes")
        except Exception as exc:
            logger.warning(f"Failed to cache '{key}': {exc}")

    logger.info(f"✅ Pre-generated {len(_TTS_CACHE)} TTS responses")


def _convert_raw_to_wav(
    raw_pcm: bytes, sample_rate: int = 22050, channels: int = 1, sample_width: int = 2
) -> bytes:
    """
    Convert raw PCM audio to proper WAV format.

    Args:
        raw_pcm: Raw PCM audio bytes (16-bit signed integers)
        sample_rate: Audio sample rate (Piper default: 22050 Hz)
        channels: Number of audio channels (1 = mono)
        sample_width: Bytes per sample (2 = 16-bit)

    Returns:
        bytes: Proper WAV file with RIFF header
    """

    # Create WAV file in memory
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)  # 1 = Mono
        wav_file.setsampwidth(sample_width)  # 2 = 16-bit
        wav_file.setframerate(sample_rate)  # 22050 Hz
        wav_file.writeframes(raw_pcm)  # Write audio data

    wav_buffer.seek(0)
    wav_bytes = wav_buffer.read()

    logger.debug(f"Converted {len(raw_pcm)} bytes PCM → {len(wav_bytes)} bytes WAV")

    return wav_bytes


def _synthesize_piper(text: str) -> bytes:
    """
    Generate proper WAV audio using Piper TTS.

    Returns valid WAV files, not raw PCM!

    Args:
        text: Text to convert to speech

    Returns:
        bytes: WAV audio data (playable in browsers and media players)

    Raises:
        RuntimeError: If TTS generation fails
    """

    # Step 1: Generate RAW PCM audio with Piper
    cmd = [
        "piper",
        "--model",
        "/app/models/en_US-lessac-medium.onnx",
        "--length_scale",
        "0.9",  # 10% faster speech
        "--output-raw",  # Outputs raw PCM (needs WAV conversion)
    ]

    try:
        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=10,
        )

        raw_audio = result.stdout

        if not raw_audio or len(raw_audio) == 0:
            raise RuntimeError("Piper produced no audio output")

        logger.debug(f"Piper generated {len(raw_audio)} bytes of raw PCM")

        # Step 2: Convert RAW PCM to proper WAV format
        wav_audio = _convert_raw_to_wav(raw_audio)

        #  Validate WAV header
        if not wav_audio.startswith(b"RIFF"):
            raise RuntimeError("WAV conversion failed - invalid header")

        logger.info(f"✅ TTS generated: {len(wav_audio)} bytes (WAV format)")

        return wav_audio

    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if exc.stderr else "Unknown error"
        logger.error(f"Piper subprocess failed: {error_msg}")
        raise RuntimeError(f"TTS generation failed: {error_msg}") from exc
    except subprocess.TimeoutExpired:
        logger.error("Piper TTS timed out")
        raise RuntimeError("TTS generation timed out")
    except RuntimeError:
        #  Re-raise RuntimeError with original message (preserves "Piper produced no audio output")
        raise
    except Exception as exc:
        logger.exception("Unexpected TTS error")
        raise RuntimeError("TTS generation failed") from exc


def synthesize_tts(text: str, cache_key: Optional[str] = None) -> bytes:
    """
    Synthesize TTS with optional caching.

     Now returns proper WAV files!

    Args:
        text: Text to synthesize
        cache_key: If provided, check cache first (e.g., "hello", "error")

    Returns:
        bytes: WAV audio data (playable in any media player)

    Raises:
        RuntimeError: If TTS generation fails
    """
    text = _truncate_text(text, max_chars=200)
    # Check cache first
    if cache_key and cache_key in _TTS_CACHE:
        logger.debug(f"🎯 Using cached TTS for '{cache_key}'")
        return _TTS_CACHE[cache_key]

    #  Limit text length for faster generation (preserve word boundaries)
    MAX_CHARS = 400
    if len(text) > MAX_CHARS:
        # Find last space before MAX_CHARS to avoid cutting mid-word
        truncated = text[:MAX_CHARS]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        text = truncated + "..."
        logger.debug(f"Truncated text to {len(text)} chars")

    # Generate audio
    audio_bytes = _synthesize_piper(text)

    # Store in cache if key provided
    if cache_key:
        _TTS_CACHE[cache_key] = audio_bytes
        logger.debug(f"Cached TTS for '{cache_key}'")

    return audio_bytes


def _truncate_text(text: str, max_chars: int = 200) -> str:
    """
    Truncate text to a maximum character length while preserving word boundaries.

    Ensures that truncation does not cut off mid-word by finding the last space
    before the character limit and appending "..." to indicate truncation.

    Args:
        text: The text string to truncate
        max_chars: Maximum number of characters allowed (default: 200)

    Returns:
        str: Truncated text with "..." appended if truncation occurred,
             or original text if it's within the limit
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."
