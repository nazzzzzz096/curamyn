from app.chat_service.services.llm_service import _extract_text


class Dummy:
    text = "Hello there!"


def test_extract_direct_text():
    assert _extract_text(Dummy()) == "Hello there!"
