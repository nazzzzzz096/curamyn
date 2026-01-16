import pytest
from app.chat_service.services.safety_guard import check_output_safety, SafetyViolation


def test_diagnosis_blocked():
    with pytest.raises(SafetyViolation):
        check_output_safety(user_text="Do I have cancer?")
