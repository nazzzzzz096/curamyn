from app.chat_service.services.ocr_cleaner import clean_ocr_text


def test_ocr_removes_short_lines():
    cleaned = clean_ocr_text("aa\nblood report")
    assert "blood report" in cleaned
