"""
Signup page UI.

Provides centered signup form with dark theme styling.
"""

from nicegui import ui

from frontend.api.auth_client import signup_user
from frontend.state.app_state import state


def show_signup_page() -> None:
    """
    Render signup page at the center with dark theme.
    """

    with ui.column().classes(
        "w-screen h-screen items-center justify-center bg-[#0f172a]"
    ):
        with ui.card().classes(
            "w-[380px] bg-[#111827] text-white shadow-xl rounded-2xl p-6"
        ):

            # -------- TITLE --------
            ui.label("Create Curamyn Account").classes(
                "text-2xl font-bold text-center mb-6"
            )

            # -------- INPUTS --------
            email = ui.input(
                label="Email",
                placeholder="you@example.com",
            ).props("outlined dense dark").classes("w-full")

            password = ui.input(
                label="Password",
                placeholder="••••••••",
                password=True,
                password_toggle_button=True,
            ).props("outlined dense dark").classes("w-full mt-3")

            # -------- SIGNUP BUTTON --------
            ui.button(
                "Sign up",
                on_click=lambda: _handle_signup(
                    email.value,
                    password.value,
                ),
            ).classes(
                "w-full mt-5 bg-emerald-600 hover:bg-emerald-500 "
                "text-white font-semibold rounded-lg"
            )

            # -------- FOOTER --------
            ui.separator().classes("my-4")

            ui.label("Already have an account?").classes(
                "text-center text-gray-400 text-sm"
            )

            ui.button(
                "Login",
                on_click=lambda: ui.navigate.to("/login"),
            ).props("flat").classes("w-full text-emerald-400")


def _handle_signup(email: str, password: str) -> None:
    """
    Create user account and redirect to onboarding.
    """
    try:
        signup_user(email=email, password=password)

        ui.notify("Account created successfully!", type="positive")
        ui.navigate.to("/login")

    except Exception as exc:
        ui.notify(
            f"Signup failed: {exc}",
            type="negative",
        )
