from app.chat_service.services.orchestrator.input_router import route_input


def test_text_routing():
    text, ctx = route_input(
        input_type="text",
        text="Hello",
        audio=None,
        image=None,
        image_type=None,
    )
    assert text == "Hello"
