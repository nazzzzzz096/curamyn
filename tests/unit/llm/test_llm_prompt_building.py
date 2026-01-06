from app.chat_service.services.llm_service import analyze_text
from unittest.mock import patch

def test_llm_fallback_used_when_gemini_response_invalid():
    with patch(
        "app.chat_service.services.llm_service.client.models.generate_content"
    ) as mock_gen:
        mock_gen.return_value.text = None  # Force invalid response

        result = analyze_text(text="Hi")

        assert result["response_text"] == "I'm here with you."
