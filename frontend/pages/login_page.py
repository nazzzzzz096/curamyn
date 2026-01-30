"""
Login page UI.

Provides centered login form with dark theme styling.
"""

from nicegui import ui
from frontend.api.consent_client import get_consent
from frontend.api.auth_client import login_user
from frontend.state.app_state import state
from frontend.utils.logger import get_logger
import json

logger = get_logger(__name__)


def show_login_page() -> None:
    """
    Render the login page with a centered dark-themed form.
    """
    ui.dark_mode().enable()

    # -------- PAGE CONTAINER --------
    with ui.column().classes(
        "w-screen h-screen items-center justify-center bg-[#0f172a]"
    ):
        with ui.card().classes(
            "w-[380px] bg-[#111827] text-white " "shadow-xl rounded-2xl p-6"
        ):

            # -------- TITLE --------
            ui.label("Curamyn").classes("text-2xl font-bold text-center mb-1")
            ui.label("Welcome back").classes("text-sm text-gray-400 text-center mb-6")

            # -------- INPUTS --------
            email = (
                ui.input(
                    label="Email",
                    placeholder="you@example.com",
                )
                .props("outlined dense dark")
                .classes("w-full")
            )

            password = (
                ui.input(
                    label="Password",
                    placeholder="••••••••",
                    password=True,
                    password_toggle_button=True,
                )
                .props("outlined dense dark")
                .classes("w-full mt-3")
            )

            # -------- LOGIN BUTTON --------
            login_btn = ui.button(
                "Login",
                on_click=lambda: _handle_login(
                    email.value,
                    password.value,
                    login_btn,
                ),
            ).classes(
                "w-full mt-5 bg-emerald-600 "
                "hover:bg-emerald-500 text-white font-semibold rounded-lg"
            )

            # -------- FOOTER --------
            ui.separator().classes("my-4")

            ui.label("Don't have an account?").classes(
                "text-center text-gray-400 text-sm"
            )

            ui.button(
                "Create account",
                on_click=lambda: ui.navigate.to("/signup"),
            ).props("flat").classes("w-full text-emerald-400")


def _handle_login(
    email: str,
    password: str,
    button,
) -> None:
    """
    Authenticate the user and navigate to onboarding or chat.
    """

    if state.logging_in:
        return

    if not email or not password:
        ui.notify("Please enter both email and password", type="warning")
        return

    state.logging_in = True
    button.disable()

    try:
        token_data = login_user(email=email, password=password)

        state.token = token_data["access_token"]
        state.user_id = token_data.get("user_id")
        state.session_id = token_data.get("session_id")

        ui.run_javascript(f"localStorage.setItem('access_token', '{state.token}');")

        # Load user consent
        try:
            state.consent = get_consent(token=state.token)
        except Exception:
            logger.exception("Failed to load consent")
            state.consent = {
                "memory": False,
                "voice": False,
                "document": False,
                "image": False,
            }

        ui.notify("Login successful", type="positive")

        # CHECK ONBOARDING COMPLETION STATUS
        try:
            from frontend.api.onboarding_client import check_onboarding_status

            onboarding_status = check_onboarding_status(token=state.token)

            if onboarding_status.get("completed", False):
                # User has completed onboarding → go to chat
                logger.info("User has completed onboarding, redirecting to chat")
                ui.navigate.to("/chat")
            else:
                # User hasn't completed onboarding → go to onboarding
                logger.info(
                    "User hasn't completed onboarding, redirecting to onboarding"
                )
                ui.navigate.to("/onboarding")

        except Exception:
            logger.exception(
                "Failed to check onboarding status, defaulting to onboarding"
            )
            # On error, send to onboarding to be safe
            ui.navigate.to("/onboarding")

    except Exception:
        ui.notify("Invalid email or password", type="negative")
        logger.exception("Login failed")

    finally:
        state.logging_in = False
        button.enable()
