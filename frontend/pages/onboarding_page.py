from nicegui import ui
from frontend.api.onboarding_client import get_next_question, submit_answer
from frontend.api.consent_client import update_consent
from frontend.state.app_state import state
from frontend.utils.logger import get_logger

logger = get_logger(__name__)


def show_onboarding_page() -> None:
    """
    Render the onboarding page.

    Displays one question at a time and navigates
    the user to chat upon completion.
    """
    if not state.token:
        ui.navigate.to("/login")
        return

    with ui.element("div").classes(
        "flex justify-center items-center min-h-screen w-full bg-[#0f172a]"
    ):
        card = ui.card().classes(
            "w-full max-w-2xl bg-[#111827] text-white shadow-xl rounded-2xl p-8"
        )
        render_question(card)


def render_question(card) -> None:
    """Clear the card and render the next onboarding question."""
    card.clear()

    try:
        data = get_next_question(token=state.token)
    except Exception:
        ui.notify("Failed to load onboarding question", type="negative")
        logger.exception("Failed to load onboarding question")
        return

    if data.get("completed"):
        finalize_onboarding()
        return

    with card:
        ui.label(data["question_text"]).classes(
            "text-xl font-semibold mb-8 text-center"
        )

        answer_input = (
            ui.input(label="Your answer (optional)")
            .props("outlined dense dark")
            .classes("w-full")
        )

        with ui.row().classes("justify-between mt-8"):
            skip_btn = ui.button("Skip").props("flat").classes("text-gray-400")
            next_btn = ui.button("Next").classes(
                "bg-emerald-600 text-white font-semibold"
            )

            skip_btn.on_click(
                lambda: submit_and_continue(card, data["question_key"], "")
            )
            next_btn.on_click(
                lambda: submit_and_continue(
                    card,
                    data["question_key"],
                    answer_input.value,
                )
            )


def submit_and_continue(card, question_key: str, answer: str):
    """
     Submit the user's answer (or skip) and load the next question.

    Args:
        card: UI container holding the question content.
        question_key: Identifier for the current question.
        value: User answer or None if skipped.
    """
    card.disable()

    try:
        submit_answer(
            token=state.token,
            question_key=question_key,
            answer=answer,
        )
        render_question(card)
    except Exception:
        ui.notify("Failed to submit answer", type="negative")
        logger.exception("Submit failed")
    finally:
        card.enable()


def finalize_onboarding():
    logger.info("Onboarding completed")

    # ✅ Set default consent preferences
    try:
        update_consent(
            token=state.token,
            consent_data={
                "memory": True,  # Enable memory by default
                "voice": False,
                "document": False,
                "image": False,
            },
        )

        state.consent = {
            "memory": True,
            "voice": False,
            "document": False,
            "image": False,
        }

    except Exception:
        logger.exception("Failed to set default consent")

    ui.notify("Onboarding completed 🎉", type="positive")

    ui.run_javascript(
        """
        setTimeout(() => {
            window.location.href = "/chat";
        }, 500);
    """
    )
