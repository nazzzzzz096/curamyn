from app.chat_service.services.tts_service import _soften_for_voice

def test_soften_text():
    assert "." not in _soften_for_voice("Hello.")
