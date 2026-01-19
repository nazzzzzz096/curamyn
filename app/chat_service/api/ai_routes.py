"""
AI interaction API routes.

Handles multimodal AI interactions (text, voice, image)
through a unified orchestration pipeline.

Responsibilities:
- Input validation
- Orchestration delegation
- Safe persistence of chat history
"""

import uuid
import base64
from typing import Optional, Dict, Any
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
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Handle a multimodal AI interaction and persist chat history.

    Flow:
    - Validate input
    - Generate session ID if missing
    - Run orchestration pipeline
    - Persist user and AI messages
    """

    user_id = user["sub"]
    session_id = session_id or str(uuid.uuid4())

    # -----------------------------
    # VALIDATION
    # -----------------------------
    if input_type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid input_type")

    if response_mode not in ALLOWED_RESPONSE_MODES:
        raise HTTPException(status_code=400, detail="Invalid response_mode")

    if input_type == "text" and not text:
        raise HTTPException(status_code=400, detail="Text input required")

    if input_type == "audio" and not audio:
        raise HTTPException(status_code=400, detail="Audio file required")

    if input_type == "image" and not image:
        raise HTTPException(status_code=400, detail="Image file required")

    # -----------------------------
    # READ FILES
    # -----------------------------
    audio_bytes = await audio.read() if audio else None
    image_bytes = await image.read() if image else None

    # -----------------------------
    # RUN ORCHESTRATION
    # -----------------------------
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

    # -----------------------------
    # PERSIST CHAT MESSAGES
    # -----------------------------
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # TODO: Enforce consent flags before storing audio/image data

        # ----- USER MESSAGE -----
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

        elif input_type == "image" and image_bytes:
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

        elif input_type == "audio" and audio_bytes:
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

        # ----- AI MESSAGE (TEXT) -----
        ai_message = result.get("message")
        if ai_message and ai_message.strip():
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "Curamyn",
                    "type": "text",
                    "text": ai_message,
                    "sent": False,
                    "timestamp": timestamp,
                },
            )

        # ----- AI MESSAGE (AUDIO, OPTIONAL) -----
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
            "Chat messages stored successfully",
            extra={
                "session_id": session_id,
                "user_id": user_id,
            },
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
