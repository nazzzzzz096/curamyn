import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_gemini_response():
    class MockResponse:
        text = "I hear you. Want to talk about it?"
        candidates = []
    return MockResponse()


@pytest.fixture
def mock_audio_bytes():
    return b"FAKE_AUDIO"


@pytest.fixture
def mock_image_bytes():
    return b"FAKE_IMAGE"
