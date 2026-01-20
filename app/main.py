"""
Application entry point for Curamyn backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

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
from app.chat_service.services.piper_model_loader import load_piper_models_from_s3
from app.chat_service.config import settings
from app.chat_service.utils.logger import get_logger
import mlflow
import os

# ---- Map Curamyn config → MLflow expected env vars ----
os.environ["MLFLOW_TRACKING_URI"] = settings.MLFLOW_TRACKING_URI
os.environ["MLFLOW_TRACKING_USERNAME"] = settings.DAGSHUB_USERNAME
os.environ["MLFLOW_TRACKING_PASSWORD"] = settings.DAGSHUB_TOKEN

# ---- Initialize MLflow ----
mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
mlflow.set_experiment("curamyn")


logger = get_logger(__name__)
logger.info(
    "MLflow initialized | tracking_uri=%s | user=%s",
    mlflow.get_tracking_uri(),
    os.environ.get("MLFLOW_TRACKING_USERNAME"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_piper_models_from_s3()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Curamyn",
    version="1.1.0",
)

# -------------------------------------------------
# Middleware
# -------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(
        "Incoming request",
        extra={
            "method": request.method,
            "url": str(request.url),
        },
    )
    return await call_next(request)


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
