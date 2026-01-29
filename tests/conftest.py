"""
Pytest configuration and fixtures.
"""

import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables."""

    # Set required environment variables for tests
    test_env = {
        "CURAMYN_GEMINI_API_KEY": "test_gemini_key",
        "CURAMYN_DEEPGRAM_API_KEY": "test_deepgram_key",
        "CURAMYN_MONGODB_URI": "mongodb://localhost:27017",
        "CURAMYN_MONGODB_DB_NAME": "curamyn_test",
        "CURAMYN_S3_BUCKET_NAME": "test_bucket",
        "CURAMYN_S3_ACCESS_KEY": "test_access_key",
        "CURAMYN_S3_SECRET_KEY": "test_secret_key",
        "CURAMYN_S3_REGION": "us-east-1",
        "CURAMYN_SENTRY_DSN": "",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    yield

    # Cleanup
    for key in test_env:
        os.environ.pop(key, None)


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from app.chat_service.config import Settings

    return Settings(
        GEMINI_API_KEY="test_key",
        DEEPGRAM_API_KEY="test_key",
        MONGODB_URI="mongodb://localhost:27017",
        MONGODB_DB_NAME="curamyn_test",
        S3_BUCKET_NAME="test_bucket",
        S3_ACCESS_KEY="test_access",
        S3_SECRET_KEY="test_secret",
        S3_REGION="us-east-1",
    )
