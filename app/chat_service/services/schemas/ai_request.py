"""
Schemas for AI interaction requests.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    """
    AI interaction request schema.
    """

    input_type: str = Field(
        ...,
        description="Input modality: text, audio, or image",
    )
    session_id: Optional[str] = Field(
        None,
        description="Existing session ID; if omitted, a new session is created",
    )
    response_mode: str = Field(
        "text",
        description="Response mode: text or voice",
    )
    text: Optional[str] = Field(
        None,
        description="Text input (required when input_type is 'text')",
    )
    image_type: Optional[str] = Field(
        None,
        description="Image category hint (e.g. document, xray, skin)",
    )
