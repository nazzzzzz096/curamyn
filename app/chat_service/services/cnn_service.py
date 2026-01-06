"""
CNN-based image risk analysis service.

Performs non-diagnostic risk assessment on medical images.
"""
import os
import io
import time
from typing import Dict

from PIL import Image
import torch
from torchvision import transforms
from torch import nn
import mlflow

from app.chat_service.services.model_loader import load_cnn_model_from_s3
from app.chat_service.utils.logger import get_logger
from app.chat_service.config import settings

logger = get_logger(__name__)

# --------------------------------------------------
# Image preprocessing
# --------------------------------------------------
_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ]
)
# --------------------------------------------------
# MLflow setup
# --------------------------------------------------
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
mlflow.set_experiment("curamyn_llm_services")
# --------------------------------------------------
# Model cache
# --------------------------------------------------
_MODEL_CACHE: Dict[str, nn.Module] = {}


def _get_model(model_type: str) -> nn.Module:
    """Load and cache CNN model."""
    if model_type not in _MODEL_CACHE:
        logger.info("Loading CNN model", extra={"model_type": model_type})

        model = load_cnn_model_from_s3(
            model_type=model_type,
            bucket=settings.S3_BUCKET_NAME,
        )
        model.eval()

        _MODEL_CACHE[model_type] = model

    return _MODEL_CACHE[model_type]


def predict_risk(
    *,
    image_type: str,
    image_bytes: bytes,
) -> Dict[str, float | str]:
    """
    Perform risk analysis on a medical image.
    """
    model_map = {
        "xray": "x_ray",
        "skin": "skin",
    }

    if image_type not in model_map:
        logger.warning(
            "Unsupported image type",
            extra={"image_type": image_type},
        )
        raise ValueError(f"Unsupported image_type: {image_type}")

    start_time = time.time()

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.error("Failed to decode image")
        raise ValueError("Invalid image data") from exc

    # ---------------- MLflow Tracking ----------------
    with mlflow.start_run(nested=True):
        mlflow.set_tag("service", "cnn_inference")
        mlflow.set_tag("image_type", image_type)
        mlflow.set_tag("model_type", model_map[image_type])

        try:
            tensor = _TRANSFORM(image).unsqueeze(0)
            model = _get_model(model_map[image_type])

            with torch.no_grad():
                logits = model(tensor)
                probability = torch.sigmoid(logits).item()

        except Exception as exc:
            mlflow.set_tag("status", "failed")
            logger.exception("CNN inference failed")
            raise RuntimeError("Model inference failed") from exc

        risk = (
            "needs_attention"
            if probability >= settings.RISK_THRESHOLD
            else "normal"
        )

        latency = time.time() - start_time

        # -------- MLflow logs (SAFE) --------
        mlflow.log_metric("confidence", probability)
        mlflow.log_metric("latency_sec", latency)
        mlflow.set_tag("risk", risk)
        mlflow.set_tag("status", "success")

    logger.info(
        "CNN inference completed",
        extra={
            "image_type": image_type,
            "risk": risk,
            "confidence": round(probability, 3),
        },
    )

    return {
        "risk": risk,
        "confidence": round(probability, 3),
    }
