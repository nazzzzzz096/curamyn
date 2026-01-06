"""
CNN model loader from S3.
"""

import io
import boto3
import torch
from torchvision import models
from botocore.exceptions import BotoCoreError, ClientError

from app.chat_service.utils.logger import get_logger
from app.chat_service.config import settings

logger = get_logger(__name__)

_LOADED_MODELS: dict[str, torch.nn.Module] = {}


def _get_s3_client():
    """Create and return an S3 client."""
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def load_cnn_model_from_s3(
    model_type: str,
    bucket: str,
) -> torch.nn.Module:
    """
    Load a CNN model from S3 and cache it in memory.
    """
    if model_type in _LOADED_MODELS:
        logger.debug(
            "Using cached CNN model",
            extra={"model_type": model_type},
        )
        return _LOADED_MODELS[model_type]

    model_file_map = {
        "skin": "skin_risk_resnet18.pt",
        "x_ray": "xray_risk_resnet18.pt",
    }

    if model_type not in model_file_map:
        raise ValueError(f"Unknown model_type: {model_type}")

    key = f"models/{model_type}/{model_file_map[model_type]}"

    logger.info(
        "Loading CNN model from S3",
        extra={"bucket": bucket, "key": key},
    )

    try:
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=bucket, Key=key)
        model_bytes = response["Body"].read()

    except (BotoCoreError, ClientError) as exc:
        logger.exception("Failed to download model from S3")
        raise RuntimeError("Model download failed") from exc

    model = models.resnet18(pretrained=False)
    model.fc = torch.nn.Linear(model.fc.in_features, 1)

    checkpoint = torch.load(io.BytesIO(model_bytes), map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    _LOADED_MODELS[model_type] = model
    return model
