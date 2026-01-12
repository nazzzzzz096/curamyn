"""
Application configuration.

Centralized environment-based settings using Pydantic v2.
"""

from typing import List

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    # --------------------
    # Environment
    # --------------------
    ENV: str = "dev"

    # --------------------
    # CORS
    # --------------------
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        description="Allowed CORS origins for frontend",
    )

    # --------------------
    # Database
    # --------------------
    MONGO_URI: str
    MONGO_DB: str

    # --------------------
    # Auth / Security
    # --------------------
    JWT_SECRET: str
    STORAGE_SECRET: str

    # --------------------
    # LLM
    # --------------------
    GEMINI_API_KEY: str

    # --------------------
    # MLflow / DAGsHub
    # --------------------
    MLFLOW_TRACKING_URI: str
    DAGSHUB_USERNAME: str
    DAGSHUB_TOKEN: str

    # --------------------
    # AWS
    # --------------------
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"

    # --------------------
    # S3
    # --------------------
    S3_BUCKET_NAME: str

    # --------------------
    # CNN settings
    # --------------------
    RISK_THRESHOLD: float = 0.5

    model_config = ConfigDict(
        env_file=".env",
        env_prefix="CURAMYN_", 
        extra="forbid",        
    )


settings = Settings()
