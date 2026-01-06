"""
Schemas for AI interaction responses.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AIResponse(BaseModel):
    """
    AI interaction response schema.
    """

    session_id: str = Field(
        ...,
        description="Session identifier",
    )
    message: str = Field(
        ...,
        description="User-facing response text",
    )
    audio: Optional[str] = Field(
        None,
        description="Base64-encoded audio (if voice response is enabled)",
    )
    disclaimer: Optional[str] = Field(
        None,
        description="Medical or safety disclaimer when applicable",
    )
