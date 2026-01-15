from typing import Optional, Dict
from app.chat_service.repositories.session_repositories import (
    get_onboarding_from_session,
)

def get_onboarding_context(user_id: str) -> Optional[str]:
    """
    Returns a compact, privacy-safe onboarding summary for chat context.
    """
    answers = get_onboarding_from_session(user_id)
    if not answers:
        return None

    # Keep it SHORT and NEUTRAL
    lines = []

    if answers.get("sleep"):
        lines.append(f"Sleep: {answers['sleep']}")

    if answers.get("emotional_state"):
        lines.append(f"Emotional baseline: {answers['emotional_state']}")

    if answers.get("medications"):
        lines.append(f"Medications: {answers['medications']}")

    return "; ".join(lines) if lines else None
