"""
Frontend configuration.

Loads frontend-specific environment variables only.
Safely ignores unrelated backend environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    """
    Frontend application settings.

    Environment variables must be prefixed with:
        CURAMYN_

    Example:
        CURAMYN_API_BASE_URL=http://localhost:8000
    """

    API_BASE_URL: str = Field(
        default="http://backend:8000",
        description="Base URL for backend API",
        min_length=1,
    )

    model_config = ConfigDict(
        env_file=".env",
        env_prefix="CURAMYN_",
        extra="ignore",
    )


settings = Settings()
