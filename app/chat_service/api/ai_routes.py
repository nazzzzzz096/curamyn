"""
AI interaction API routes.

Handles multimodal AI interactions (text, voice, image) through
a unified orchestration pipeline.
"""

import uuid
from typing import Optional
from base64 import b64encode
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from datetime import datetime,timezone
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
    """
    Run a multimodal AI interaction.

    Supported input types:
    - text
    - audio
    - image

    Args:
        input_type (str): Type of user input.
        session_id (Optional[str]): Existing session ID or None.
        response_mode (str): Response format (text or voice).
        text (Optional[str]): Text input.
        image_type (Optional[str]): Image MIME/type hint.
        audio (Optional[UploadFile]): Audio input file.
        image (Optional[UploadFile]): Image input file.
        user (dict): Authenticated user context.

    Returns:
        dict: AI-generated response with session metadata.

    Raises:
        HTTPException: If validation fails or processing errors occur.
    """
    user_id = user["sub"]

    # ---- Session handling ----
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(
            "New AI session created",
            extra={"session_id": session_id, "user_id": user_id},
        )

    # ---- Input validation ----
    if input_type not in ALLOWED_INPUT_TYPES:
        logger.warning(
            "Invalid input_type",
            extra={"input_type": input_type, "session_id": session_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input_type",
        )

    if response_mode not in ALLOWED_RESPONSE_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid response_mode",
        )

    if input_type == "text" and not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text input required",
        )

    if input_type == "audio" and not audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file required",
        )

    if input_type == "image" and not image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file required",
        )

    logger.info(
        "AI interaction started",
        extra={
            "session_id": session_id,
            "user_id": user_id,
            "input_type": input_type,
            "response_mode": response_mode,
        },
    )

    try:
        audio_bytes = await audio.read() if audio else None
        image_bytes = await image.read() if image else None
        if input_type == "text" and text:
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "text": text,
                    "sent": True,
                    "type": "text",
                    "created_at": datetime.now(timezone.utc).isoformat(),
           },
        )
        if input_type == "image" and image_bytes:
            encoded = b64encode(image_bytes).decode()
            mime_type = image.content_type or "image/png"

            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "type": "image",
                    "data": f"data:{mime_type};base64,{encoded}",
                    "sent": True,
                    "created_at": datetime.utcnow().isoformat(),
            },
        )
        if input_type == "audio" and audio_bytes:
            append_chat_message(
                user_id=user_id,
                session_id=session_id,
                message={
                    "author": "You",
                    "type": "audio",
                    "sent": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        result = run_interaction(
            input_type=input_type,
            session_id=session_id,
            user_id=user_id,
            text=text,
            audio=audio_bytes,
            image=image_bytes,
            image_type=image_type,
            response_mode=response_mode,
        )
        response_text = result.get("response_text") or result.get("message")

        if response_text:
            append_chat_message(
            user_id=user_id,
            session_id=session_id,
            message={
            "author": "Curamyn",
            "text": response_text,
            "sent": False,
            "type": "text",
            "created_at": datetime.utcnow().isoformat(),
            },
         )

        result["session_id"] = session_id

        logger.info(
            "AI interaction completed",
            extra={"session_id": session_id, "user_id": user_id},
        )

        return result

    except Exception as exc:
        logger.exception(
            "AI interaction failed",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "input_type": input_type,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI interaction failed",
        ) from exc

