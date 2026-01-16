"""
AI interaction API routes.

Handles multimodal AI interactions (text, voice, image)
through a unified orchestration pipeline.
"""

import uuid
from typing import Optional
from datetime import datetime, timezone
import base64

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


# ======================================================
# ROUTES
# ======================================================


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
    """
    Handle multimodal AI interaction and persist chat history.

    - Generates session_id if missing
    - Runs orchestration pipeline
    - Stores user + AI messages in MongoDB
    """
    user_id = user["sub"]

    if not session_id:
        session_id = str(uuid.uuid4())

    # ---------- Validation ----------
    if input_type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid input_type")

    if response_mode not in ALLOWED_RESPONSE_MODES:
        raise HTTPException(status_code=400, detail="Invalid response_mode")

    if input_type == "audio":
        if not audio:
            raise HTTPException(status_code=400, detail="Audio file required")
        response_mode = "voice"

    if input_type == "text" and not text:
        raise HTTPException(status_code=400, detail="Text input required")

    if input_type == "image" and not image:
        raise HTTPException(status_code=400, detail="Image file required")

    # ---------- Read files ----------
    audio_bytes = await audio.read() if audio else None
    image_bytes = await image.read() if image else None

    # ---------- Run AI ----------
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

    logger.debug(
        "AI interaction completed",
        extra={
            "session_id": session_id,
            "input_type": input_type,
            "response_keys": list(result.keys()),
        },
    )

    # ---------- Persist Chat ----------
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # -------- USER MESSAGE --------
        if input_type == "text":
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "type": "text",
                    "text": text,
                    "sent": True,
                    "timestamp": timestamp,
                },
            )

        elif input_type == "image":
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "type": "image",
                    "image_data": encoded_image,
                    "mime_type": image.content_type or "image/png",
                    "sent": True,
                    "timestamp": timestamp,
                },
            )

        elif input_type == "audio":
            encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "type": "audio",
                    "audio_data": encoded_audio,
                    "mime_type": audio.content_type or "audio/webm",
                    "sent": True,
                    "timestamp": timestamp,
                },
            )

        # -------- AI MESSAGE (TEXT) --------
        if result.get("message"):
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "Curamyn",
                    "type": "text",
                    "text": result["message"],
                    "sent": False,
                    "timestamp": timestamp,
                },
            )

        # -------- AI MESSAGE (AUDIO, optional) --------
        if result.get("audio_base64"):
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "Curamyn",
                    "type": "audio",
                    "audio_data": result["audio_base64"],
                    "mime_type": "audio/mpeg",
                    "sent": False,
                    "timestamp": timestamp,
                },
            )

        logger.info(
            f"Chat messages stored successfully | session_id={session_id} | user_id={user_id}"
        )

    except Exception:
        logger.exception(
            "Failed to store chat messages",
            extra={"session_id": session_id},
        )

    return {
        **result,
        "session_id": session_id,
    }
