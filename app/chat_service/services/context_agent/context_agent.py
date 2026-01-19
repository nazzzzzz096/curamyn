"""
Context Agent.

Builds conversation-aware input for the LLM using session history,
summaries, and SAFE abstractions of onboarding data.

This module intentionally avoids injecting raw medical facts
(conditions, medications) into the LLM to prevent diagnostic behavior.
"""

from typing import List

from app.chat_service.utils.logger import get_logger
from app.chat_service.services.context_agent.summary_provider import (
    get_session_summary,
)
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.repositories.onboarding_repository import (
    get_onboarding_profile,
)

logger = get_logger(__name__)


class ContextAgent:
    """
    Injects optional, non-clinical context into LLM input.

    The context is designed to improve emotional awareness and
    conversational continuity without influencing medical reasoning
    or diagnosis.
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
        """
        Build conversation-aware input for the LLM.

        This method merges recent conversation history, session summaries,
        and abstracted onboarding signals to guide tone and sensitivity
        while ensuring the response focuses on the user's current message.

        Args:
            user_input: The current user message.
            input_type: The type of input (text, audio, image).
            user_id: Optional unique user identifier.
            session_id: Active session identifier.
            session_state: Current session state containing recent context.

        Returns:
            A formatted string containing optional contextual information
            followed by the current user message.
        """

        # -------------------------------
        # 1. SHORT-TERM CONTEXT (RECENT CHAT)
        # -------------------------------
        recent_turns = session_state.last_messages[-6:]
        history_block = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in recent_turns
            if m.get("content")
        )

        # -------------------------------
        # 2. SAFE USER AWARENESS (ONBOARDING)
        # -------------------------------
        awareness_lines: List[str] = []

        if user_id:
            try:
                profile = get_onboarding_profile(user_id)
                logger.debug(
                    "Onboarding profile loaded",
                    extra={"user_id": user_id},
                )
            except Exception:
                logger.exception(
                    "Failed to load onboarding profile",
                    extra={"user_id": user_id},
                )
                profile = None

            if profile:
                if profile.get("emotional_baseline"):
                    awareness_lines.append(
                        "Respond in a calm, reassuring, and non-alarming manner."
                    )

                if profile.get("known_conditions"):
                    awareness_lines.append(
                        "Avoid medical assumptions and keep guidance general."
                    )

                if profile.get("medications"):
                    awareness_lines.append(
                        "Do not reference medicines or medical treatments."
                    )

                if profile.get("age_range"):
                    awareness_lines.append(
                        "Use clear and respectful language appropriate for adults."
                    )

                if profile.get("gender"):
                    awareness_lines.append(
                        "Avoid gender-based assumptions in responses."
                    )

        awareness_block = "\n".join(awareness_lines)

        # -------------------------------
        # 3. LONG-TERM CONTEXT (SESSION SUMMARY)
        # -------------------------------
        summary_text = ""
        if user_id:
            try:
                summary = get_session_summary(
                    user_id=user_id,
                    session_id=session_id,
                )
                if summary:
                    summary_text = summary.get("summary_text", "")
                    logger.debug(
                        "Session summary injected",
                        extra={"session_id": session_id},
                    )
            except Exception:
                logger.exception(
                    "Failed to load session summary",
                    extra={"session_id": session_id},
                )

        # -------------------------------
        # 4. NON-MEDICAL SYSTEM HINTS
        # -------------------------------
        hints: List[str] = []

        if session_state.last_image_analysis:
            hints.append(
                "The user previously shared an image related to their concern."
            )

        if session_state.last_document_text:
            hints.append("The user previously shared a document.")

        hint_block = "\n".join(hints)

        # -------------------------------
        # 5. CONTEXT ASSEMBLY (ONLY IF PRESENT)
        # -------------------------------
        blocks: List[str] = []

        if awareness_block:
            blocks.append(f"Support considerations:\n{awareness_block}")

        if history_block:
            blocks.append(f"Conversation so far:\n{history_block}")

        if summary_text:
            blocks.append(f"Previous session summary:\n{summary_text}")

        if hint_block:
            blocks.append(f"System hints:\n{hint_block}")

        if not blocks:
            logger.debug(
                "No context injected; returning raw user input",
                extra={"session_id": session_id},
            )
            return user_input

        context_text = "\n\n".join(blocks)

        logger.debug(
            "Context injected into LLM input",
            extra={
                "session_id": session_id,
                "context_blocks": len(blocks),
            },
        )

        return f"""
--- OPTIONAL CONTEXT (FOR AWARENESS ONLY) ---

{context_text}

--- END CONTEXT ---

IMPORTANT:
Respond primarily to the CURRENT user message.
Follow all assistant rules strictly.

User message:
{user_input}
""".strip()
