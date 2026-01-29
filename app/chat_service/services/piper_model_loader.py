"""
Piper TTS model loader from S3.
"""

import boto3
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError

from app.chat_service.utils.logger import get_logger
from app.chat_service.config import settings

logger = get_logger(__name__)

_PIPER_LOADED = False

BUCKET_NAME = settings.S3_BUCKET_NAME
S3_PREFIX = "models/voice"

FILES = [
    "en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json",
]

LOCAL_MODEL_DIR = Path("/app/models")


def load_piper_models_from_s3() -> None:
    """
    Download Piper model files from S3 to local filesystem.
    This must be called BEFORE PiperVoice.load().
    """
    global _PIPER_LOADED

    if _PIPER_LOADED:
        logger.debug("Piper models already loaded")
        return

    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    for filename in FILES:
        local_path = LOCAL_MODEL_DIR / filename
        if local_path.exists():
            logger.info(
                "Piper model file already exists",
                extra={"file": filename},
            )
            continue

        key = f"{S3_PREFIX}/{filename}"

        try:
            logger.info(
                "Downloading Piper model from S3",
                extra={"bucket": BUCKET_NAME, "key": key},
            )

            s3.download_file(
                BUCKET_NAME,
                key,
                str(local_path),
            )

        except (BotoCoreError, ClientError) as exc:
            logger.exception(
                "Failed to download Piper model from S3",
                extra={"file": filename},
            )
            raise RuntimeError("Piper model download failed") from exc

    _PIPER_LOADED = True
    logger.info("All Piper models downloaded successfully")
