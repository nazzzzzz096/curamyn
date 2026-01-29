"""
OPTIMIZED voice chat pipeline.

Latency breakdown:
- STT (Deepgram): ~500ms  ✅ (was 2-3s with Whisper)
- LLM (Gemini):   ~2-3s
- TTS (Piper):    ~1.5s   ✅ (was 3-4s)
Total:            ~4-5s   ✅ (was 8-11s)
"""

import asyncio
import base64
import time
from typing import Optional

from app.chat_service.services.deepgram_service import transcribe_audio  # ✅ NEW
from app.chat_service.services.llm_service import analyze_text
from app.chat_service.services.tts_streamer import synthesize_tts
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def _get_cache_key(text: str) -> Optional[str]:
    """Check if text matches a cached response."""
    text_lower = text.lower().strip()

    # Common greetings
    if text_lower in ["hello", "hi", "hey", "good morning", "good afternoon"]:
        return "hello"

    # Goodbyes
    if text_lower in ["bye", "goodbye", "see you", "take care"]:
        return "goodbye"

    # Errors
    if text_lower in ["what", "huh", "sorry"]:
        return "error"

    return None


def normalized_response_text(text: str, severity: str) -> str:
    """Normalize response text with appropriate ending."""
    text = text.strip()

    if text.endswith("."):
        return text

    endings = {
        "low": "That makes sense.",
        "moderate": "You're doing the best you can.",
        "high": "You don't have to go through this alone.",
    }

    return f"{text}. {endings.get(severity, 'I hear you.')}"


async def voice_chat_pipeline(
    audio_bytes: bytes,
    user_id: Optional[str] = None,
    session_state=None,
) -> dict:
    """
    OPTIMIZED voice chat pipeline.

    Args:
        audio_bytes: Raw audio bytes from browser (WebM/WAV)
        user_id: Optional user identifier
        session_state: Session context (images, documents)

    Returns:
        dict: {
            "message": str,
            "audio_base64": str,
            "severity": str,
            "intent": str,
            "tts_failed": bool,
            "latency": dict,  # ✅ Performance metrics
        }
    """
    start_time = time.time()
    latency = {}

    logger.info("🎤 Voice pipeline started (OPTIMIZED)")

    # ============================================================
    # STEP 1: SPEECH-TO-TEXT (Deepgram - FAST!)
    # ============================================================
    stt_start = time.time()

    try:
        user_text = await transcribe_audio(audio_bytes)
    except Exception as exc:
        logger.exception("STT failed")
        return {
            "message": "Sorry, I couldn't hear you clearly. Please try again.",
            "audio_base64": None,
            "tts_failed": True,
            "latency": {"total": time.time() - start_time},
        }

    latency["stt"] = time.time() - stt_start
    logger.info(f"⏱️ STT latency: {latency['stt']:.2f}s")

    if not user_text or len(user_text.strip()) < 2:
        logger.warning("Transcription returned empty or very short text")
        return {
            "message": "Sorry, I didn't catch that. Could you repeat?",
            "audio_base64": None,
            "tts_failed": True,
            "latency": latency,
        }

    logger.info(f"📝 Transcribed: '{user_text[:80]}...'")

    # ============================================================
    # CHECK FOR CACHED RESPONSES (Instant!)
    # ============================================================
    cache_key = _get_cache_key(user_text)

    if cache_key:
        logger.info(f"🎯 Using cached response for: {cache_key}")

        messages = {
            "hello": "Hello! How can I help you today?",
            "goodbye": "Take care! I'm here whenever you need me.",
            "error": "Sorry, I didn't catch that clearly. Could you try again?",
        }

        message = messages.get(cache_key, "I'm here with you.")

        try:
            audio_bytes_out = await asyncio.to_thread(
                synthesize_tts,
                message,
                cache_key,  # ✅ Use cache
            )

            return {
                "message": message,
                "audio_base64": base64.b64encode(audio_bytes_out).decode(),
                "severity": "low",
                "intent": "greeting",
                "tts_failed": False,
                "latency": {"total": time.time() - start_time, "stt": latency["stt"]},
            }
        except Exception as exc:
            logger.warning("Cached TTS failed, falling back to LLM response")
            pass

    # ============================================================
    # INJECT SESSION CONTEXT
    # ============================================================
    context_lines = []

    if session_state:
        # Document context
        if session_state.last_document_text:
            doc_preview = session_state.last_document_text[:300]
            context_lines.append(
                f"""
[DOCUMENT UPLOADED]
The user uploaded a medical document earlier.
Preview: {doc_preview}...
"""
            )

        # Image context
        if session_state.last_image_analysis:
            img_analysis = session_state.last_image_analysis
            img_type = session_state.last_image_type or "medical image"
            context_lines.append(
                f"""
[IMAGE UPLOADED]
Type: {img_type}
Risk: {img_analysis.get('risk')}
Confidence: {img_analysis.get('confidence')}
"""
            )

    # Build enriched prompt
    if context_lines:
        full_context = "\n".join(context_lines)
        enriched_text = f"""
{full_context}

INSTRUCTIONS:
- Only mention document/image if user explicitly asks
- Otherwise respond naturally to their question
- Keep response under 40 words (voice output)

User's voice message:
{user_text}
"""
    else:
        enriched_text = user_text

    # ============================================================
    # STEP 2: LLM ANALYSIS
    # ============================================================
    llm_start = time.time()

    try:
        llm_result = await asyncio.to_thread(
            analyze_text,
            text=enriched_text,
            user_id=user_id,
        )
    except Exception as exc:
        logger.exception("LLM analysis failed")
        return {
            "message": "I'm having trouble processing that. Please try again.",
            "audio_base64": None,
            "tts_failed": True,
            "latency": latency,
        }

    latency["llm"] = time.time() - llm_start
    logger.info(f"⏱️ LLM latency: {latency['llm']:.2f}s")

    response_text = llm_result.get("response_text", "")
    severity = llm_result.get("severity", "low")

    if not response_text:
        response_text = "I'm here with you."

    # ✅ LIMIT LENGTH for faster TTS
    if len(response_text) > 200:
        response_text = response_text[:200].rsplit(" ", 1)[0] + "..."
    raw_text = response_text.strip()
    spoken_text = normalized_response_text(raw_text, severity)

    logger.info(f"🤖 Response: '{spoken_text[:80]}...'")

    # ============================================================
    # STEP 3: TEXT-TO-SPEECH
    # ============================================================
    tts_start = time.time()

    try:
        audio_bytes_out = await asyncio.to_thread(
            synthesize_tts,
            spoken_text,
        )

        if not audio_bytes_out or len(audio_bytes_out) == 0:
            raise ValueError("TTS returned empty audio")

        latency["tts"] = time.time() - tts_start
        latency["total"] = time.time() - start_time

        logger.info(
            f"⏱️ TTS latency: {latency['tts']:.2f}s | " f"Total: {latency['total']:.2f}s"
        )

        audio_base64 = base64.b64encode(audio_bytes_out).decode()

        return {
            "message": spoken_text,
            "audio_base64": audio_base64,
            "severity": severity,
            "intent": llm_result.get("intent"),
            "tts_failed": False,
            "latency": latency,
        }

    except Exception as exc:
        logger.exception("TTS generation failed")

        latency["tts"] = time.time() - tts_start
        latency["total"] = time.time() - start_time

        return {
            "message": spoken_text,
            "audio_base64": None,
            "severity": severity,
            "intent": llm_result.get("intent"),
            "tts_failed": True,
            "latency": latency,
        }
