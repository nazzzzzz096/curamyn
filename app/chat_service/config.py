"""
Application configuration.

Centralized environment-based settings using Pydantic v2.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # --------------------
    # Environment
    # --------------------
    ENV: str = "dev"

    # --------------------
    # Database
    # --------------------
    MONGO_URI: str
    MONGO_DB: str

    # --------------------
    # Auth / Security
    # --------------------
    JWT_SECRET: str

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
        extra="forbid" , 

    )


settings = Settings()
