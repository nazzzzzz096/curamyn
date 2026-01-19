import os
from app.chat_service.services.whisper_service import transcribe


def test_whisper_transcribe_returns_text(monkeypatch):
    # Force test environment
    monkeypatch.setenv("CURAMYN_ENV", "test")

    result = transcribe(b"fake-audio-bytes")

    assert result == "hello"
