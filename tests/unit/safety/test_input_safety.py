import pytest
from app.chat_service.services.safety_guard import check_input_safety, SafetyViolation

def test_voice_consent_block():
    with pytest.raises(SafetyViolation):
        check_input_safety("audio", {"voice": False})
