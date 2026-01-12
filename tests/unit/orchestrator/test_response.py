import pytest

from app.chat_service.services.orchestrator.response_builder import (
    build_response,
)


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


def test_safe_fallback_on_exception(monkeypatch):
    def broken_finalize(*args, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(
        "app.chat_service.services.orchestrator.response_builder.finalize_spoken_text",
        broken_finalize,
    )

    response = build_response(
        llm_result={"response_text": "Hi", "severity": "low"},
        context={},
        response_mode="text",
        consent={},
    )

    assert "Something went wrong" in response["message"]
