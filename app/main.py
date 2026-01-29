"""
Application entry point for Curamyn backend.
"""

import os
import asyncio
import mlflow
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded


from app.chat_service.api.ai_routes import router as ai_router
from app.chat_service.api.chat_history_router import router as chat_history_router
from app.chat_service.api.memory_routes import router as memory_router
from app.chat_service.api.voice_stream_routes import router as voice_stream_router
from app.consent_service.router import router as consent_router
from app.question_service.router import router as question_router
from app.user_service.router import router as user_router

from app.chat_service.services.piper_model_loader import load_piper_models_from_s3
from app.chat_service.config import settings
from app.chat_service.utils.logger import get_logger
from app.core.rate_limit import limiter
from app.core.security import verify_access_token
from app.core.audit_middleware import AuditMiddleware
from app.chat_service.services.tts_streamer import init_tts_cache

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

logger = get_logger(__name__)

# =========================================================
# MLflow Setup
# =========================================================
os.environ["MLFLOW_TRACKING_URI"] = settings.MLFLOW_TRACKING_URI
os.environ["MLFLOW_TRACKING_USERNAME"] = settings.DAGSHUB_USERNAME
os.environ["MLFLOW_TRACKING_PASSWORD"] = settings.DAGSHUB_TOKEN


# =========================================================
# Lifespan
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")

    app.state.piper_loaded = False
    app.state.tts_cache_ready = False

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment("curamyn")

    try:
        load_piper_models_from_s3()
        app.state.piper_loaded = True
        logger.info("Piper models loaded")
    except Exception as e:
        logger.error("Piper model load failed", extra={"error": str(e)})

    async def warm_tts():
        try:
            init_tts_cache()
            app.state.tts_cache_ready = True
            logger.info("TTS cache ready")
        except Exception as e:
            logger.error("TTS cache failed", extra={"error": str(e)})

    asyncio.create_task(asyncio.to_thread(warm_tts))

    yield


# =========================================================
# App Init
# =========================================================
app = FastAPI(
    lifespan=lifespan,
    title="Curamyn",
    version="1.1.0",
)

# =========================================================
# CORS
# =========================================================
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =========================================================
# Rate Limiting (MUST be before CORS)
# =========================================================
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# =========================================================
# Attach user → request.state (for user-based limits)
# =========================================================
@app.middleware("http")
async def attach_user_to_state(request: Request, call_next):
    request.state.user = None

    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        try:
            token = auth.split(" ", 1)[1]
            request.state.user = verify_access_token(token)
        except Exception as e:
            logger.warning("Invalid access token", extra={"error": str(e)})

    return await call_next(request)


# =========================================================
# Request Logging
# =========================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        "Incoming request",
        extra={
            "method": request.method,
            "url": str(request.url),
        },
    )
    return await call_next(request)


# =========================================================
# Routers
# =========================================================
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
        ],
    },
)


# =========================================================
# Health
# =========================================================
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "piper_loaded": getattr(app.state, "piper_loaded", False),
        "tts_cache_ready": getattr(app.state, "tts_cache_ready", False),
    }


# Initialize Sentry
if settings.ENV == "prod":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),  # Get from sentry.io
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        profiles_sample_rate=0.1,  # 10% for profiling
        environment=settings.ENV,
    )
    logger.info("Sentry initialized for error tracking")
