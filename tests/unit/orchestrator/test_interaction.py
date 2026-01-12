import pytest
from app.chat_service.services.orchestrator.orchestrator import run_interaction


@pytest.mark.asyncio
async def test_audio_without_transcription():
    response = await run_interaction(
        input_type="audio",
        session_id="test_session",
        user_id=None,
        text=None,
        audio=b"fake",
        image=None,
        image_type=None,
        response_mode="text",
    )
    assert "could not understand" in response["message"].lower()


@pytest.mark.asyncio
async def test_non_health_query():
    response = await run_interaction(
        input_type="text",
        session_id="test_session",
        user_id=None,
        text="Tell me a joke",
        audio=None,
        image=None,
        image_type=None,
        response_mode="text",
    )
    assert response["intent"] == "refusal"
