"""
Frontend configuration.

Reads only frontend-related environment variables.
Ignores backend env variables safely.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    API_BASE_URL: str = "http://localhost:8000"

    # ✅ CRITICAL FIX
    model_config = ConfigDict(
        env_file=".env",
        env_prefix="CURAMYN_",
        extra="ignore",   # <-- THIS LINE FIXES EVERYTHING
    )


settings = Settings()
