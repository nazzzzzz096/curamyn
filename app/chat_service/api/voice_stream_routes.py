from fastapi import APIRouter, WebSocket
from app.chat_service.services.tts_streamer import stream_tts

router = APIRouter()


@router.websocket("/ai/voice-stream")
async def voice_stream(ws: WebSocket):
    await ws.accept()

    data = await ws.receive_json()
    text = data.get("text", "")

    async for audio_chunk in stream_tts(text):
        await ws.send_bytes(audio_chunk)

    await ws.close()
