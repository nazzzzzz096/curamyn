from nicegui import ui

from frontend.api.onboarding_client import (
    get_next_question,
    submit_answer,
)
from frontend.state.app_state import state
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def show_onboarding_page() -> None:
    """
    Render the onboarding page.

    Displays one question at a time and navigates
    the user to chat upon completion.
    """
    if not state.token:
        logger.warning("Onboarding page accessed without authentication")
        ui.navigate.to("/login")
        return

    with ui.element("div").classes(
        "flex items-center justify-center min-h-screen bg-[#0f172a]"
    ):
        card = ui.card().classes(
            "w-[520px] bg-[#111827] text-white "
            "shadow-xl rounded-2xl p-6"
        )

        render_question(card)


def render_question(card) -> None:
    """
    Clear the card and render the next onboarding question.
    """
    logger.debug("Rendering onboarding question")

    card.clear()

    try:
        data = get_next_question(token=state.token)
    except Exception:
        logger.exception("Failed to fetch onboarding question")
        ui.notify(
            "Failed to load onboarding question",
            type="negative",
        )
        return

    if data.get("completed"):
        logger.info("Onboarding completed")
        ui.notify(
            "Onboarding completed",
            type="positive",
        )
        ui.navigate.to("/chat")
        return

    # -------- QUESTION --------
    ui.label(data["question_text"]).classes(
        "text-lg font-semibold mb-6"
    )

    # -------- INPUT --------
    answer_input = (
        ui.input(label="Your answer (optional)")
        .props("outlined dense dark")
        .classes("w-full")
    )

    # -------- ACTIONS --------
    with ui.row().classes("justify-between mt-8"):
        ui.button(
            "Skip",
            on_click=lambda: submit_and_reload(
                card=card,
                question_key=data["question_key"],
                value=None,
            ),
        ).props("flat").classes("text-gray-400")

        next_btn = ui.button(
            "Next",
            on_click=lambda: submit_and_reload(
                card=card,
                question_key=data["question_key"],
                value=answer_input.value,
            ),
        ).classes(
            "bg-emerald-600 text-white font-semibold"
        )


def submit_and_reload(
    *,
    card,
    question_key: str,
    value: str | None,
) -> None:
    """
    Submit the user's answer (or skip) and load the next question.

    Args:
        card: UI container holding the question content.
        question_key: Identifier for the current question.
        value: User answer or None if skipped.
    """
    logger.info(
        "Submitting onboarding answer",
        extra={
            "question_key": question_key,
            "has_answer": value is not None,
        },
    )

    try:
        submit_answer(
            token=state.token,
            question_key=question_key,
            answer=value,
        )
    except Exception:
        logger.exception("Failed to submit onboarding answer")
        ui.notify(
            "Failed to submit answer. Please try again.",
            type="negative",
        )
        return

    # Replace content, do not append
    render_question(card)
