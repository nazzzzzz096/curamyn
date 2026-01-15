import pytest

from app.chat_service.services.orchestrator.response_builder import (
    build_response,
)
from app.chat_service.services.orchestrator.orchestrator import run_interaction

def test_document_response():
    response = build_response(
        llm_result={
            "intent": "document_understanding",
            "response_text": "Summary text",
        },
        context={},
        response_mode="text",
        consent={},
    )
    assert response["message"] == "Summary text"


def test_image_risk_response():
    response = build_response(
        llm_result={},
        context={"image_analysis": {"risk": "needs_attention"}},
        response_mode="text",
        consent={},
    )
    assert "medical attention" in response["message"]

import pytest
from app.chat_service.services.orchestrator.orchestrator import run_interaction

@pytest.mark.asyncio
async def test_safe_fallback_on_exception(monkeypatch):
    def broken_route_llm(*args, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(
        "app.chat_service.services.orchestrator.orchestrator._route_llm",
        broken_route_llm,
    )

    response = await run_interaction(
        input_type="text",
        session_id="test_session",
        user_id=None,
        text="hello",
        audio=None,
        image=None,
        image_type=None,
        response_mode="text",
    )

    assert "something went wrong" in response["message"].lower()


