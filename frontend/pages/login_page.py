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
    if not email or not password:
        ui.notify(
            "Please enter both email and password",
            type="warning",
        )
        return

    logger.info(
        "Login attempt initiated",
        extra={"email": email},
    )

    button.disable()

    try:
        token_data = login_user(
            email=email,
            password=password,
        )

        # =====================
        # Store auth state
        # =====================
        state.token = token_data["access_token"]
        state.user_id = token_data.get("user_id")
        state.session_id = token_data.get("session_id")

        ui.run_javascript(
            f"""
            localStorage.setItem('access_token', '{state.token}');
            """
        )

        # =====================
        # 🔥 LOAD CONSENT FROM BACKEND
        # =====================
        try:
            consent = get_consent(token=state.token)
            state.consent = consent
            logger.info("Consent loaded", extra={"consent": consent})

            # Optional: persist in browser
            ui.run_javascript(
                f"""
                localStorage.setItem('consent', '{json.dumps(consent)}');
                """
            )

        except Exception:
            # If no consent exists yet
            state.consent = {
                "memory": False,
                "voice": False,
                "document": False,
                "image": False,
            }
            logger.info("No existing consent found")

        ui.notify(
            "Login successful",
            type="positive",
        )

        # =====================
        # 🔥 NAVIGATION LOGIC
        # =====================
        if any(state.consent.values()):
            # Consent already given → skip onboarding
            ui.navigate.to("/chat")
        else:
            # First-time user → onboarding
            ui.navigate.to("/onboarding")

    except Exception:
        logger.exception("Login failed")
        ui.notify(
            "Invalid email or password",
            type="negative",
        )

    finally:
        button.enable()
