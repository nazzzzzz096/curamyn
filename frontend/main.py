"""
Application entrypoint and route definitions.

Registers all frontend pages and starts the NiceGUI app.
"""

import os

from nicegui import ui

from frontend.pages.login_page import show_login_page
from frontend.pages.signup_page import show_signup_page
from frontend.pages.onboarding_page import show_onboarding_page
from frontend.pages.chat_page import show_chat_page
from frontend.state.app_state import state
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def _enable_dark_mode() -> None:
    """Enable global dark mode."""
    ui.dark_mode().enable()


@ui.page("/")
def root() -> None:
    """Root route – redirects to login."""
    _enable_dark_mode()
    logger.debug("Root route accessed; redirecting to /login")
    ui.navigate.to("/login")


@ui.page("/login")
def login() -> None:
    """Login page route."""
    _enable_dark_mode()
    logger.debug("Login page accessed")
    show_login_page()


@ui.page("/signup")
def signup() -> None:
    """Signup page route."""
    _enable_dark_mode()
    logger.debug("Signup page accessed")
    show_signup_page()


@ui.page("/onboarding")
def onboarding() -> None:
    """Onboarding page route."""
    _enable_dark_mode()

    if not state.token:
        logger.warning("Unauthorized access to onboarding; redirecting to login")
        ui.navigate.to("/login")
        return

    logger.debug("Onboarding page accessed")
    show_onboarding_page()


@ui.page("/chat")
def chat() -> None:
    """Chat page route."""
    _enable_dark_mode()

    logger.debug("Chat page accessed")
    show_chat_page()


def start_app() -> None:
    """
    Start the NiceGUI application.
    """
    logger.info("Starting Curamyn frontend application")

    ui.run(
        title="Curamyn",
        reload=False,
        storage_secret=os.getenv(
            "CURAMYN_STORAGE_SECRET",
            "dev-secret",
        ),
    )


if __name__ == "__main__":
    start_app()
