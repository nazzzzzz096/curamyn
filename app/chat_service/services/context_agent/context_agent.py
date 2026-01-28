"""
Context Agent.

Builds conversation-aware input for the LLM using session history,
summaries, and SAFE abstractions of onboarding data.

This module intentionally avoids injecting raw medical facts
(conditions, medications) into the LLM to prevent diagnostic behavior.
"""

from typing import List
from datetime import datetime, timezone

from app.chat_service.utils.logger import get_logger
from app.chat_service.services.context_agent.summary_provider import (
    get_session_summary,
)
from app.chat_service.services.orchestrator.session_state import SessionState
from app.chat_service.repositories.onboarding_repository import (
    get_onboarding_profile,
)

logger = get_logger(__name__)


def _is_topic_similar(current_text: str, previous_topics: List[str]) -> tuple:
    """
    Check if current user message relates to any previous health topics.

    Args:
        current_text: Current user message
        previous_topics: List of health topics from previous sessions

    Returns:
        (is_similar, matching_topics)
    """
    if not previous_topics:
        return False, []

    current_lower = current_text.lower()

    # Define topic synonyms for better matching
    topic_synonyms = {
        "headache": ["headache", "head pain", "migraine", "head hurt", "head ache"],
        "anxiety": [
            "anxiety",
            "anxious",
            "worried",
            "nervous",
            "panic",
            "stress",
            "stressed",
        ],
        "insomnia": [
            "insomnia",
            "sleep",
            "can't sleep",
            "trouble sleeping",
            "sleep issues",
            "sleeping",
        ],
        "fatigue": [
            "tired",
            "fatigue",
            "exhausted",
            "low energy",
            "weakness",
            "energy",
        ],
        "depression": ["sad", "depressed", "depression", "down", "low mood", "unhappy"],
        "stomach": ["stomach", "nausea", "digestive", "belly", "gut", "tummy"],
        "back pain": ["back pain", "back hurt", "spine", "lower back", "back ache"],
        "chest": ["chest", "chest pain", "heart", "breathing"],
        "fever": ["fever", "temperature", "hot", "chills"],
        "cough": ["cough", "coughing", "throat"],
    }

    matching = []

    for prev_topic in previous_topics:
        prev_topic_lower = prev_topic.lower()

        # Direct match
        if prev_topic_lower in current_lower:
            matching.append(prev_topic)
            continue

        # Synonym match
        for base_term, synonyms in topic_synonyms.items():
            if prev_topic_lower in synonyms:
                if any(syn in current_lower for syn in synonyms):
                    matching.append(prev_topic)
                    break

    return len(matching) > 0, matching


def _format_time_ago(dt: datetime) -> str:
    """
    Format datetime as human-readable time ago.

    Args:
        dt: Datetime object

    Returns:
        Human-readable string like "2 days ago"
    """
    now = datetime.now(timezone.utc)

    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    if days > 0:
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"


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

        This method merges:
        - Previous session summaries (cross-session memory)
        - Recent conversation history (current session)
        - Session summaries (long-term context)
        - Abstracted onboarding signals

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
        # 1. PREVIOUS SESSIONS (SMART FILTERING!)
        # -------------------------------
        previous_sessions_block = ""

        if user_id:
            try:
                from app.chat_service.repositories.session_repositories import (
                    get_recent_session_summaries,
                )

                recent_summaries = get_recent_session_summaries(
                    user_id=user_id,
                    limit=5,  # Get more, filter to relevant ones
                    days=14,  # Look back 2 weeks
                )

                if recent_summaries:
                    # ✅ STEP 1: Filter summaries by topic relevance
                    relevant_summaries = []

                    for summary_doc in recent_summaries:
                        summary = summary_doc.get("summary", {})
                        health_topics = summary.get("health_topics", [])

                        # Check if current message relates to past topics
                        is_similar, matching = _is_topic_similar(
                            user_input, health_topics
                        )

                        if is_similar:
                            summary_doc["matching_topics"] = matching
                            relevant_summaries.append(summary_doc)

                    # ✅ STEP 2: Only inject if we found relevant past conversations
                    if relevant_summaries:
                        previous_lines = []
                        previous_lines.append("📋 RELEVANT PAST CONVERSATIONS:")

                        for idx, summary_doc in enumerate(
                            relevant_summaries[:3], 1
                        ):  # Max 3
                            summary = summary_doc.get("summary", {})
                            created_at = summary_doc.get("created_at")
                            matching_topics = summary_doc.get("matching_topics", [])

                            # Format timestamp
                            if created_at:
                                time_ago = _format_time_ago(created_at)
                                previous_lines.append(
                                    f"\n🕐 Session {idx} ({time_ago}):"
                                )
                            else:
                                previous_lines.append(f"\n🕐 Session {idx}:")

                            # Add matching topics
                            previous_lines.append(
                                f"  📌 Related topics: {', '.join(matching_topics)}"
                            )

                            # Add summary text
                            summary_text = summary.get("summary_text")
                            if summary_text:
                                previous_lines.append(f"  💬 {summary_text}")

                            # Add context details if available
                            context_details = summary.get("context_details", {})
                            if context_details:
                                if context_details.get("duration"):
                                    previous_lines.append(
                                        f"  ⏱️  Duration mentioned: {context_details['duration']}"
                                    )
                                if (
                                    context_details.get("actions_taken")
                                    and context_details["actions_taken"]
                                    != "none mentioned"
                                ):
                                    previous_lines.append(
                                        f"  💊 Actions taken: {context_details['actions_taken']}"
                                    )

                            # Add severity context
                            severity = summary.get("severity_peak")
                            if severity and severity in ["moderate", "high"]:
                                previous_lines.append(
                                    f"  ⚠️  Previous severity: {severity}"
                                )

                        if previous_lines:
                            previous_sessions_block = "\n".join(previous_lines)

                            logger.info(
                                "Injected relevant past sessions",
                                extra={
                                    "session_id": session_id,
                                    "relevant_count": len(relevant_summaries),
                                    "matching_topics": [
                                        s.get("matching_topics")
                                        for s in relevant_summaries
                                    ],
                                },
                            )
                    else:
                        logger.debug(
                            "No topic match found with previous sessions",
                            extra={"session_id": session_id},
                        )

            except Exception:
                logger.exception(
                    "Failed to load previous session summaries",
                    extra={"session_id": session_id},
                )

        # -------------------------------
        # 2. SHORT-TERM CONTEXT (RECENT CHAT)
        # -------------------------------
        recent_turns = session_state.last_messages[-6:]
        history_block = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in recent_turns
            if m.get("content")
        )

        # -------------------------------
        # 3. SAFE USER AWARENESS (ONBOARDING)
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
        # 4. LONG-TERM CONTEXT (CURRENT SESSION SUMMARY)
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
        # 5. NON-MEDICAL SYSTEM HINTS
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
        # 6. CONTEXT ASSEMBLY (ONLY IF PRESENT)
        # -------------------------------
        blocks: List[str] = []

        # ✅ NEW: Previous sessions first
        if previous_sessions_block:
            blocks.append(
                f"Previous conversations (for continuity):\n{previous_sessions_block}"
            )

        if awareness_block:
            blocks.append(f"Support considerations:\n{awareness_block}")

        if history_block:
            blocks.append(f"Current conversation:\n{history_block}")

        if summary_text:
            blocks.append(f"Current session summary:\n{summary_text}")

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
                "has_previous_sessions": bool(previous_sessions_block),
            },
        )

        return f"""
--- OPTIONAL CONTEXT (FOR AWARENESS ONLY) ---

{context_text}

--- END CONTEXT ---

IMPORTANT:
1. If the user references previous conversations ("last time", "we talked about"), acknowledge it using the previous session summaries above
2. Respond primarily to the CURRENT user message
3. Use previous context to provide continuity of care
4. Follow all assistant rules strictly

User message:
{user_input}
""".strip()
