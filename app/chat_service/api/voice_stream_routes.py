from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.chat_service.services.tts_streamer import synthesize_tts
from app.chat_service.utils.logger import get_logger
from app.core.rate_limit import limiter

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ai/voice-stream")
@limiter.limit("10/minute")
async def voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for voice synthesis.
    """
    await websocket.accept()
    logger.info("Voice stream WebSocket accepted")

    try:
        data = await websocket.receive_json()
        text = data.get("text", "")

        if not text.strip():
            await websocket.send_json({"error": "Empty text"})
            return

        audio_bytes = synthesize_tts(text)

        if not audio_bytes:
            await websocket.send_json({"error": "No audio generated"})
            return

        await websocket.send_bytes(audio_bytes)
        logger.info("Voice stream sent successfully")

    except WebSocketDisconnect:
        logger.info("Voice stream WebSocket disconnected")

    except Exception as exc:
        logger.exception("Voice stream error")
        await websocket.send_json({"error": str(exc)})

    finally:
        await websocket.close()
