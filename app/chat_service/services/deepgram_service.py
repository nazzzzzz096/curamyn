"""
Fast speech-to-text using Deepgram API.

Replaces Whisper (2-3s) with Deepgram (0.5-0.8s).
"""

import os
import asyncio
from typing import Optional
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from app.chat_service.services.whisper_service import transcribe
from app.chat_service.utils.logger import get_logger
import time
from app.observability.metrics import (
    STT_REQUEST_LATENCY,
    STT_REQUESTS_TOTAL,
    STT_ERRORS_TOTAL,
    STT_FALLBACKS_TOTAL,
)

logger = get_logger(__name__)

# Singleton client
_DEEPGRAM_CLIENT: Optional[DeepgramClient] = None


def get_deepgram_client() -> DeepgramClient:
    """Get or create Deepgram client."""
    global _DEEPGRAM_CLIENT

    if _DEEPGRAM_CLIENT is None:
        api_key = os.getenv("CURAMYN_DEEPGRAM_API_KEY")

        if not api_key:
            raise RuntimeError(
                "CURAMYN_DEEPGRAM_API_KEY not found in environment variables. "
                "Get one from https://console.deepgram.com"
            )

        _DEEPGRAM_CLIENT = DeepgramClient(api_key=api_key)
        logger.info("✅ Deepgram client initialized")

    return _DEEPGRAM_CLIENT


async def transcribe_audio(audio_bytes: bytes, use_fallback: bool = True) -> str:
    """
    Transcribe audio using Deepgram (with Whisper fallback).

    Args:
        audio_bytes: Audio file bytes (WebM, WAV, MP3, etc.)
        use_fallback: If True, use Whisper if Deepgram fails

    Returns:
        str: Transcribed text

    Raises:
        RuntimeError: If all transcription methods fail
    """
    if not audio_bytes:
        return ""

    # ------------------ DEEPGRAM ------------------
    deepgram_start = time.time()

    try:
        client = get_deepgram_client()

        payload: FileSource = {"buffer": audio_bytes}
        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            punctuate=True,
        )

        response = await asyncio.to_thread(
            client.listen.prerecorded.v("1").transcribe_file,
            payload,
            options,
        )

        transcript = response.results.channels[0].alternatives[0].transcript.strip()

        if not transcript:
            raise ValueError("empty transcript")

        STT_REQUESTS_TOTAL.labels(
            engine="deepgram",
            status="success",
        ).inc()

        return transcript

    except ValueError:
        STT_ERRORS_TOTAL.labels(
            engine="deepgram",
            error_type="empty_transcript",
        ).inc()

        STT_REQUESTS_TOTAL.labels(
            engine="deepgram",
            status="failure",
        ).inc()

        logger.warning("Deepgram returned empty transcript")

    except Exception:
        STT_ERRORS_TOTAL.labels(
            engine="deepgram",
            error_type="api_error",
        ).inc()

        STT_REQUESTS_TOTAL.labels(
            engine="deepgram",
            status="failure",
        ).inc()

        logger.warning("Deepgram failed", exc_info=True)

    finally:
        STT_REQUEST_LATENCY.labels(
            engine="deepgram",
        ).observe(time.time() - deepgram_start)

    # ------------------ FALLBACK TO WHISPER ------------------
    if not use_fallback:
        raise RuntimeError("Deepgram failed and fallback disabled")

    STT_FALLBACKS_TOTAL.labels(
        from_engine="deepgram",
        to_engine="whisper",
    ).inc()

    whisper_start = time.time()
    try:
        result = transcribe(audio_bytes)

        STT_REQUESTS_TOTAL.labels(
            engine="whisper",
            status="success",
        ).inc()

        return result

    except Exception:
        STT_ERRORS_TOTAL.labels(
            engine="whisper",
            error_type="whisper_failed",
        ).inc()

        STT_REQUESTS_TOTAL.labels(
            engine="whisper",
            status="failure",
        ).inc()

        raise RuntimeError("All STT failed")

    finally:
        STT_REQUEST_LATENCY.labels(
            engine="whisper",
        ).observe(time.time() - whisper_start)


def transcribe_sync(audio_bytes: bytes) -> str:
    """
    Synchronous wrapper for backward compatibility.

    Args:
        audio_bytes: Audio file bytes

    Returns:
        str: Transcribed text
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        transcript = loop.run_until_complete(transcribe_audio(audio_bytes))
        loop.close()
        return transcript
    except Exception as exc:
        logger.exception("Sync transcription failed")
        return ""
