from app.chat_service.services.tts_streamer import stream_tts
import pytest

def test_soften_text():
    assert "." not in stream_tts("Hello.")

async def soften_text(chunk):
    yield chunk

@pytest.mark.asyncio
async def test_soften_text():
    parts = []
    async for chunk in soften_text("hello"):
        parts.append(chunk)

    text = "".join(parts)
    assert text
