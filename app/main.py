"""
Application entry point for Curamyn.
"""

from fastapi import FastAPI

from app.chat_service.api.ai_routes import router as ai_router
from app.consent_service.router import router as consent_router
from app.question_service.router import router as question_router
from app.user_service.router import router as user_router
from app.chat_service.api.memory_routes import router as memory_router
from app.chat_service.api.chat_history_router import router as chat_history_router

app = FastAPI(
    title="Curamyn",
    version="1.1.0",
)

# ---- Register API routes ----
app.include_router(user_router)
app.include_router(consent_router)
app.include_router(question_router)
app.include_router(ai_router)
app.include_router(memory_router)
app.include_router(chat_history_router)

@app.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Application health status.
    """
    return {"status": "ok"}

