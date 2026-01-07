def test_llm_uses_fallback_when_response_invalid(monkeypatch):
    from app.chat_service.services import llm_service

    class FakeClient:
        class models:
            @staticmethod
            def generate_content(*args, **kwargs):
                return None  # invalid Gemini response

    monkeypatch.setattr(
        llm_service,
        "_load_gemini",
        lambda: (FakeClient(), None),
    )

    result = llm_service.analyze_text(text="Hello")

    assert result["response_text"] == "I'm here with you."

