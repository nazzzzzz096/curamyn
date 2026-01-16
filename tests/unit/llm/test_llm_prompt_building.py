def test_llm_fallback_used_when_gemini_response_invalid(monkeypatch):
    from app.chat_service.services import llm_service

    class FakeClient:
        class models:
            @staticmethod
            def generate_content(*args, **kwargs):
                return None

    monkeypatch.setattr(
        llm_service,
        "_load_gemini",
        lambda: (FakeClient(), None),
    )

    result = llm_service.analyze_text(text="How are you?")

    assert result["response_text"] == "I'm here with you."
