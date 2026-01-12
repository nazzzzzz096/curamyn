"""
Application entry point for Curamyn backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat_service.api.ai_routes import router as ai_router
from app.chat_service.api.chat_history_router import (
    router as chat_history_router,
)
from app.chat_service.api.memory_routes import (
    router as memory_router,
)
from app.chat_service.api.voice_stream_routes import (
    router as voice_stream_router,
)
from app.consent_service.router import router as consent_router
from app.question_service.router import router as question_router
from app.user_service.router import router as user_router
from app.chat_service.config import settings
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Curamyn",
    version="1.1.0",
)

# -------------------------------------------------
# Middleware
# -------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Routers
# -------------------------------------------------

app.include_router(user_router)
app.include_router(consent_router)
app.include_router(question_router)
app.include_router(ai_router)
app.include_router(memory_router)
app.include_router(chat_history_router)
app.include_router(voice_stream_router)

logger.info(
    "API routers registered",
    extra={
        "routers": [
            "user",
            "consent",
            "question",
            "ai",
            "memory",
            "chat_history",
            "voice_stream",
        ]
    },
)

# -------------------------------------------------
# Health
# -------------------------------------------------

@app.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Application health status.
    """
    return {"status": "ok"}

