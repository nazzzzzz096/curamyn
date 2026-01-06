"""
Schemas for user consent management.
"""

from pydantic import BaseModel


class ConsentCreate(BaseModel):
    """
    Consent preferences provided by the user.

    All fields default to False to ensure privacy by default.
    """

    memory: bool = False
    voice: bool = False
    document: bool = False
    image: bool = False


class ConsentResponse(ConsentCreate):
    """
    Consent response schema including user identifier.
    """

    user_id: str
