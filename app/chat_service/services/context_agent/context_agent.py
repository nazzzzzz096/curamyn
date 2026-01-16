"""
Context Agent.

Builds conversation-aware input using session summaries.
"""

from typing import Optional
from app.chat_service.utils.logger import get_logger
from app.chat_service.services.context_agent.summary_provider import (
    get_session_summary,
)
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.repositories.onboarding_repository import get_onboarding_profile


logger = get_logger(__name__)


class ContextAgent:
    """
    Responsible for injecting conversation continuity
    into user input before LLM processing.
    """

    @staticmethod
    def build_input(
        *,
        user_input: str,
        input_type: str,
        user_id: str | None,
        session_id: str,
        session_state: SessionState,
    ) -> str:

        # -------------------------------
        # 1. SHORT-TERM CONTEXT (LIVE)
        # -------------------------------
        recent_turns = session_state.last_messages[-6:]
        history_block = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in recent_turns
            if m.get("content")
        )
        # -------------------------------
        # 2b. USER PROFILE (ONBOARDING)
        # -------------------------------
        profile_text = ""

        if user_id:
            profile = get_onboarding_profile(user_id)

            if profile:
                lines = []

                if profile.get("emotional_baseline"):
                    lines.append(f"Emotional baseline: {profile['emotional_baseline']}")

                if profile.get("medications"):
                    lines.append(f"Medications: {profile['medications']}")

                if profile.get("known_conditions"):
                    lines.append(f"Known conditions: {profile['known_conditions']}")

                profile_text = "; ".join(lines)

        # -------------------------------
        # 2. LONG-TERM CONTEXT (DB)
        # -------------------------------
        summary = None
        if user_id:
            summary = get_session_summary(
                user_id=user_id,
                session_id=session_id,
            )

        summary_text = summary.get("summary_text") if summary else ""

        # -------------------------------
        # 3. OPTIONAL IMAGE / DOC HINTS
        # -------------------------------
        hints = []
        if session_state.last_image_analysis:
            hints.append("User previously shared a medical image.")
        if session_state.last_document_text:
            hints.append("User previously shared a document.")

        hint_block = "\n".join(hints)

        # -------------------------------
        # 4. MERGED INPUT
        # -------------------------------
        if not history_block and not summary_text and not hint_block:
            return user_input

        return f"""

User background (from onboarding, if relevant):
{profile_text or "Not provided"}

Conversation so far:
{history_block}

Previous session summary:
{summary_text}

System hints:
{hint_block}

User message:
{user_input}
""".strip()
