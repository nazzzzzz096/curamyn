from unittest.mock import patch, MagicMock
from app.chat_service.services.tts_streamer import synthesize_tts


def test_synthesize_tts_returns_bytes():
    fake_chunk = MagicMock()
    fake_chunk.audio_int16_bytes = b"\x01\x02" * 200

    fake_voice = MagicMock()
    fake_voice.synthesize.return_value = [fake_chunk]

    with patch(
        "app.chat_service.services.tts_streamer._load_voice",
        return_value=fake_voice,
    ):
        audio = synthesize_tts("Hello world")

        assert isinstance(audio, (bytes, bytearray))
        assert len(audio) > 100  # WAV bytes exist
