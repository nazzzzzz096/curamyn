import os
from app.chat_service.services.educational_llm_service import explain_medical_terms


def test_explain_terms_when_gemini_unavailable(monkeypatch):
    # Force test environment
    monkeypatch.setenv("CURAMYN_ENV", "test")

    result = explain_medical_terms(
        question="What is hemoglobin?",
        document_text="Hemoglobin 13.5 g/dl",
        user_id="user123",
    )

    assert isinstance(result, dict)
    assert result["intent"] == "educational"
    assert result["severity"] == "informational"
    assert "unavailable" in result["response_text"].lower()


def test_explain_terms_with_empty_document(monkeypatch):
    monkeypatch.setenv("CURAMYN_ENV", "test")

    result = explain_medical_terms(
        question="What is WBC?",
        document_text="",
    )

    assert result["intent"] == "educational"
    assert isinstance(result["response_text"], str)


def test_explain_terms_output_is_not_empty(monkeypatch):
    monkeypatch.setenv("CURAMYN_ENV", "test")

    result = explain_medical_terms(
        question="Explain RBC",
        document_text="RBC count 4.8 million cells/µL",
    )

    assert result["response_text"]
