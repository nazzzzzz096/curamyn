"""
AI interaction API routes.

Handles multimodal AI interactions (text, voice, image)
through a unified orchestration pipeline.
"""

import uuid
from typing import Optional
from base64 import b64encode
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.chat_service.repositories.session_repositories import (
    append_chat_message,
)
from app.chat_service.services.orchestrator.orchestrator import run_interaction
from app.chat_service.utils.logger import get_logger
from app.core.dependencies import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

ALLOWED_INPUT_TYPES = {"text", "audio", "image"}
ALLOWED_RESPONSE_MODES = {"text", "voice"}


@router.post("/interact")
async def ai_interact(
    input_type: str = Form(...),
    session_id: Optional[str] = Form(None),
    response_mode: str = Form("text"),
    text: Optional[str] = Form(None),
    image_type: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
) -> dict:

    user_id = user["sub"]

    if input_type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(400, "Invalid input_type")

    if response_mode not in ALLOWED_RESPONSE_MODES:
        raise HTTPException(400, "Invalid response_mode")

    if input_type == "audio":
        if not audio:
            raise HTTPException(400, "Audio file required")
        response_mode = "voice"   #  FORCE VOICE FOR AUDIO

    if input_type == "text" and not text:
        raise HTTPException(400, "Text input required")

    if input_type == "image" and not image:
        raise HTTPException(400, "Image file required")

    audio_bytes = await audio.read() if audio else None
    image_bytes = await image.read() if image else None

    result = await run_interaction(
        input_type=input_type,
        session_id=session_id,
        user_id=user_id,
        text=text,
        audio=audio_bytes,
        image=image_bytes,
        image_type=image_type,
        response_mode=response_mode,  
    )

    return result


