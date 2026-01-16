"""
Authentication layout components.

Provides a reusable layout for authentication-related screens
(login, signup, forgot password).
"""

from typing import Callable

from nicegui import ui

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def auth_layout(title: str, content_fn: Callable[[], None]) -> None:
    """
    Render a centered authentication layout.

    Args:
        title: Title displayed at the top of the card.
        content_fn: Callback that renders the inner form content.

    Raises:
        RuntimeError: If content rendering fails.
    """
    logger.debug(
        "Rendering authentication layout",
        extra={"title": title},
    )

    with ui.element("div").classes(
        "min-h-screen flex items-center justify-center "
        "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900"
    ):
        with ui.card().classes("w-[380px] p-8 bg-slate-900 shadow-2xl"):
            ui.label(title).classes("text-2xl font-bold text-white mb-2")

            ui.label("Welcome to Curamyn").classes("text-slate-400 mb-6")

            try:
                content_fn()
            except Exception as exc:
                logger.exception(
                    "Failed to render auth layout content",
                    extra={"title": title},
                )
                ui.label("Something went wrong. Please refresh the page.").classes(
                    "text-red-400"
                )
                raise RuntimeError("Auth layout rendering failed") from exc
