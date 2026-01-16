from app.chat_service.services.safety_guard import detect_emergency


def test_emergency_detected():
    assert detect_emergency("I can't breathe")
