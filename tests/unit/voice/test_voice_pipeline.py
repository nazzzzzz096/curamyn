
from unittest.mock import patch
from app.chat_service.services.voice_pipeline_service import voice_chat_pipeline

def test_voice_pipeline_output_bytes():
    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe",
        return_value="Hi"
    ):
        with patch(
            "app.chat_service.services.voice_pipeline_service.analyze_text",
            return_value={
                "response_text": "Hello",
                "severity": "low"
            }
        ):
            with patch(
                "app.chat_service.services.voice_pipeline_service.text_to_speech",
                return_value=b"AUDIO"
            ):
                result = voice_chat_pipeline(b"audio")
                assert result == b"AUDIO"
