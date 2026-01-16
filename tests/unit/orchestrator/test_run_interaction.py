from app.chat_service.services.orchestrator.orchestrator import run_interaction
import pytest


@pytest.mark.asyncio
async def test_run_interaction_text():
    result = await run_interaction(
        input_type="text",
        session_id="s1",
        user_id=None,
        text="Hello",
        audio=None,
        image=None,
        image_type=None,
        response_mode="text",
    )
    assert "message" in result
