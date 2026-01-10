from nicegui import ui
from frontend.api.onboarding_client import get_next_question, submit_answer
from frontend.state.app_state import state


def show_onboarding_page() -> None:
    """Render onboarding page with a single question at a time."""

    with ui.element("div").classes(
        "flex items-center justify-center min-h-screen bg-[#0f172a]"
    ):

        card = ui.card().classes(
            "w-[520px] bg-[#111827] text-white shadow-xl rounded-2xl p-6"
        )

        render_question(card)


def render_question(card) -> None:
    """Clear card and render the next onboarding question."""

    # 🔑 THIS IS THE CRITICAL FIX
    card.clear()

    data = get_next_question(token=state.token)

    if data.get("completed"):
        ui.notify("Onboarding completed", type="positive")
        ui.navigate.to("/chat")
        return

    # -------- QUESTION --------
    ui.label(data["question_text"]).classes(
        "text-lg font-semibold mb-6"
    )

    # -------- INPUT --------
    answer_input = ui.input(
        label="Your answer (optional)",
    ).props("outlined dense dark").classes("w-full")

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

        ui.button(
            "Next",
            on_click=lambda: submit_and_reload(
                card=card,
                question_key=data["question_key"],
                value=answer_input.value,
            ),
        ).classes(
            "bg-emerald-600 text-white font-semibold"
        )


def submit_and_reload(*, card, question_key: str, value: str | None) -> None:
    """Submit answer (or skip) and re-render next question."""
    submit_answer(
        token=state.token,
        question_key=question_key,
        answer=value,
    )

    # 🔁 REPLACE content, do NOT append
    render_question(card)
