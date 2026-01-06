from unittest.mock import patch, MagicMock
from app.chat_service.services.cnn_service import predict_risk

def test_cnn_returns_risk():
    fake_model = MagicMock()
    fake_model.return_value = MagicMock()

    # Mock the CNN pipeline fully
    with patch(
        "app.chat_service.services.cnn_service.Image.open"
    ):
        with patch(
            "app.chat_service.services.cnn_service._TRANSFORM",
            return_value=MagicMock()
        ):
            with patch(
                "app.chat_service.services.cnn_service._get_model",
                return_value=fake_model
            ):
                with patch(
                    "torch.sigmoid",
                    return_value=MagicMock(item=lambda: 0.1)
                ):
                    result = predict_risk(
                        image_type="xray",
                        image_bytes=b"fake"
                    )

                    assert result["risk"] in {"normal", "needs_attention"}
                    assert "confidence" in result

