"""
Fast speech-to-text using Deepgram API.

Replaces Whisper (2-3s) with Deepgram (0.5-0.8s).
"""

import os
import asyncio
from typing import Optional
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

# Singleton client
_deepgram_client: Optional[DeepgramClient] = None


def get_deepgram_client() -> DeepgramClient:
    """Get or create Deepgram client."""
    global _deepgram_client

    if _deepgram_client is None:
        api_key = os.getenv("CURAMYN_DEEPGRAM_API_KEY")

        if not api_key:
            raise RuntimeError(
                "CURAMYN_DEEPGRAM_API_KEY not found in environment variables. "
                "Get one from https://console.deepgram.com"
            )

        _deepgram_client = DeepgramClient(api_key=api_key)
        logger.info("✅ Deepgram client initialized")

    return _deepgram_client


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
    if not audio_bytes or len(audio_bytes) == 0:
        logger.warning("Empty audio bytes received")
        return ""

    try:
        # ✅ TRY DEEPGRAM FIRST
        client = get_deepgram_client()

        payload: FileSource = {"buffer": audio_bytes}

        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            punctuate=True,
            diarize=False,
            utterances=False,
        )

        logger.debug(f"Starting Deepgram transcription ({len(audio_bytes)} bytes)")

        # Run in thread to not block event loop
        response = await asyncio.to_thread(
            client.listen.prerecorded.v("1").transcribe_file,
            payload,
            options,
        )

        # Extract transcript
        transcript = response.results.channels[0].alternatives[0].transcript.strip()

        if not transcript:
            raise ValueError("Deepgram returned empty transcript")

        confidence = response.results.channels[0].alternatives[0].confidence

        logger.info(
            f"✅ Deepgram transcription successful: '{transcript[:50]}...' "
            f"(confidence: {confidence:.2f})"
        )

        return transcript

    except Exception as exc:
        logger.warning(f"⚠️ Deepgram failed: {exc}")

        # ✅ FALLBACK TO WHISPER
        if use_fallback:
            logger.info("🔄 Falling back to Whisper STT...")
            try:
                from app.chat_service.services.whisper_service import transcribe

                result = transcribe(audio_bytes)
                logger.info("✅ Whisper fallback successful")
                return result
            except Exception as whisper_exc:
                logger.exception("❌ Whisper fallback also failed")
                raise RuntimeError("All STT methods failed") from whisper_exc

        raise RuntimeError("Deepgram transcription failed") from exc


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
