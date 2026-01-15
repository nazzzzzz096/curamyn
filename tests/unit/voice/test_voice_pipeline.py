import pytest
from unittest.mock import patch
from app.chat_service.services.voice_pipeline_service import voice_chat_pipeline


@pytest.mark.asyncio
async def test_voice_pipeline_output_bytes():
    async def fake_stream(_):
        yield b"AUDIO"

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe",
        return_value="hello",
    ), patch(
        "app.chat_service.services.voice_pipeline_service.analyze_text",
        return_value={"response_text": "Hello", "severity": "low"},
    ), patch(
        "app.chat_service.services.voice_pipeline_service.stream_tts",
        fake_stream,
    ):
        result = await voice_chat_pipeline(b"audio")

        assert result["audio_base64"]
        assert "hello" in result["message"].lower()
