from app.chat_service.services.llm_service import analyze_text
from unittest.mock import patch

def test_llm_uses_fallback_when_response_invalid():
    with patch(
        "app.chat_service.services.llm_service.client.models.generate_content"
    ) as mock_gen:
        mock_gen.return_value.text = ""  # Force fallback

        result = analyze_text(text="Hi")

        assert result["response_text"] == "I'm here with you."
