from unittest.mock import patch
from app.chat_service.services.whisper_service import transcribe

def test_whisper_transcribe_returns_text():
    with patch("app.chat_service.services.whisper_service.model.transcribe") as mock:
        mock.return_value = {"text": "hello"}
        assert transcribe(b"audio") == "hello"
