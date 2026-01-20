from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.chat_service.services.tts_streamer import synthesize_tts
from app.chat_service.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ai/voice-stream")
async def voice_stream(ws: WebSocket):
    """
    WebSocket endpoint for voice synthesis.
    Currently sends full audio (non-streamed).
    """
    await ws.accept()
    logger.info("Voice stream WebSocket accepted")

    try:
        data = await ws.receive_json()
        text = data.get("text", "")

        if not text.strip():
            await ws.send_json({"error": "Empty text"})
            return

        audio_bytes = synthesize_tts(text)

        if not audio_bytes:
            await ws.send_json({"error": "No audio generated"})
            return

        await ws.send_bytes(audio_bytes)

        logger.info("Voice stream sent successfully")

    except WebSocketDisconnect:
        logger.info("Voice stream WebSocket disconnected")

    except Exception as exc:
        logger.exception("Voice stream error")
        await ws.send_json({"error": str(exc)})

    finally:
        await ws.close()
