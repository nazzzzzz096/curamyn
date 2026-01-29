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
        Build conversation-aware input for the LLM with sliding window memory.
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
                    limit=5,
                    days=14,
                )

                if recent_summaries:
                    relevant_summaries = []

                    for summary_doc in recent_summaries:
                        summary = summary_doc.get("summary", {})
                        health_topics = summary.get("health_topics", [])

                        is_similar, matching = _is_topic_similar(
                            user_input, health_topics
                        )

                        if is_similar:
                            summary_doc["matching_topics"] = matching
                            relevant_summaries.append(summary_doc)

                    if relevant_summaries:
                        previous_lines = []
                        previous_lines.append("📋 RELEVANT PAST CONVERSATIONS:")

                        for idx, summary_doc in enumerate(relevant_summaries[:3], 1):
                            summary = summary_doc.get("summary", {})
                            created_at = summary_doc.get("created_at")
                            matching_topics = summary_doc.get("matching_topics", [])

                            if created_at:
                                time_ago = _format_time_ago(created_at)
                                previous_lines.append(
                                    f"\n🕐 Session {idx} ({time_ago}):"
                                )
                            else:
                                previous_lines.append(f"\n🕐 Session {idx}:")

                            previous_lines.append(
                                f"  📌 Related topics: {', '.join(matching_topics)}"
                            )

                            summary_text = summary.get("summary_text")
                            if summary_text:
                                previous_lines.append(f"  💬 {summary_text}")

                        if previous_lines:
                            previous_sessions_block = "\n".join(previous_lines)

            except Exception:
                logger.exception("Failed to load previous session summaries")

        # -------------------------------
        # 2. ✅ PERSISTENT SESSION CONTEXT (ALWAYS AVAILABLE)
        # -------------------------------
        persistent_context = ""

        # 📄 Document context (persists entire session)
        if session_state.last_document_text:
            messages_since_upload = len(session_state.all_messages) - (
                session_state.document_upload_message_index or 0
            )

            doc_preview = session_state.last_document_text[:500]
            persistent_context += f"""
[DOCUMENT UPLOADED {messages_since_upload} MESSAGES AGO]
The user uploaded a medical document during this session.
Document preview: {doc_preview}...

IMPORTANT: Only reference this document if the user explicitly asks about it.
"""
            logger.info("Injected persistent document context")

        # 🖼️ Image context (persists entire session)
        if session_state.last_image_analysis:
            messages_since_upload = len(session_state.all_messages) - (
                session_state.image_upload_message_index or 0
            )

            img_analysis = session_state.last_image_analysis
            img_type = session_state.last_image_type or "medical image"

            persistent_context += f"""
[IMAGE UPLOADED {messages_since_upload} MESSAGES AGO]
The user uploaded a {img_type} during this session.
Risk assessment: {img_analysis.get('risk', 'unknown')}
Confidence: {img_analysis.get('confidence', 0):.2%}

IMPORTANT: Only reference this image if the user explicitly asks about it.
"""
            logger.info("Injected persistent image context")

        # -------------------------------
        # 3. ✅ SLIDING WINDOW: Recent conversation (last 15 messages)
        # -------------------------------
        recent_messages = session_state.get_conversation_window(max_messages=15)
        history_block = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in recent_messages
            if m.get("content")
        )

        # -------------------------------
        # 4. ✅ CONDENSED SUMMARY: Older conversation
        # -------------------------------
        older_summary = session_state.get_condensed_history()

        # -------------------------------
        # 5. SAFE USER AWARENESS (ONBOARDING)
        # -------------------------------
        awareness_lines: List[str] = []

        if user_id:
            try:
                profile = get_onboarding_profile(user_id)
            except Exception:
                profile = None

            if profile:
                if profile.get("emotional_baseline"):
                    awareness_lines.append("Respond in a calm, reassuring manner.")
                if profile.get("known_conditions"):
                    awareness_lines.append("Avoid medical assumptions.")
                if profile.get("medications"):
                    awareness_lines.append("Do not reference medicines.")

        awareness_block = "\n".join(awareness_lines)

        # -------------------------------
        # 6. CONTEXT ASSEMBLY
        # -------------------------------
        blocks: List[str] = []

        if previous_sessions_block:
            blocks.append(f"Previous sessions:\n{previous_sessions_block}")

        if awareness_block:
            blocks.append(f"Support considerations:\n{awareness_block}")

        # ✅ Always include persistent context (documents/images)
        if persistent_context:
            blocks.append(persistent_context)

        # ✅ Include condensed older conversation
        if older_summary:
            blocks.append(f"Earlier conversation summary:\n{older_summary}")

        # ✅ Always include recent conversation
        if history_block:
            blocks.append(f"Recent conversation (last 15 messages):\n{history_block}")

        if not blocks:
            return user_input

        context_text = "\n\n".join(blocks)

        logger.debug(
            "Context built with sliding window",
            extra={
                "session_id": session_id,
                "total_messages": len(session_state.all_messages),
                "recent_messages": len(recent_messages),
                "has_document": bool(session_state.last_document_text),
                "has_image": bool(session_state.last_image_analysis),
            },
        )

        return f"""
--- CONVERSATION CONTEXT ---

{context_text}

--- END CONTEXT ---

CRITICAL INSTRUCTIONS:
1. You have access to the ENTIRE conversation history above
2. Documents and images remain accessible for the ENTIRE session
3. **DO NOT mention uploads unless the user explicitly asks about them**
4. If user asks "what about my report from earlier?" - reference the document
5. If user asks "remember that x-ray I sent 20 messages ago?" - reference the image
6. Maintain natural conversation flow

User's current message:
{user_input}
""".strip()
