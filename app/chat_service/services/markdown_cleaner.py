"""
FIXED: Clean markdown formatting from all LLM responses
"""

import re
from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


def clean_markdown(text: str) -> str:
    """
    Remove ALL markdown formatting from text.

    Removes:
    - **bold** → bold
    - *italic* → italic
    - __underline__ → underline
    - ~~strikethrough~~ → strikethrough
    - # headers → headers
    - ``` code blocks → plain text
    - [links](url) → links
    - * lists → plain text
    """
    if not text:
        return text

    # Remove code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove headers (# ## ###)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold and italic
    text = re.sub(r"\*\*\*([^\*]+)\*\*\*", r"\1", text)  # ***bold italic***
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)  # *italic*
    text = re.sub(r"__([^_]+)__", r"\1", text)  # __underline__
    text = re.sub(r"_([^_]+)_", r"\1", text)  # _italic_

    # Remove strikethrough
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # Remove links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Remove list markers
    text = re.sub(r"^\s*[\*\-\+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Remove table separators
    text = re.sub(r"\|[\s\-:]+\|", "", text)
    text = re.sub(r"\s*\|\s*", " | ", text)

    # Clean up extra whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = text.strip()

    return text


# Apply to all LLM response functions
def clean_llm_response(response_text: str) -> str:
    """
    Clean and format LLM response for user display.
    """
    if not response_text:
        return ""

    # Clean markdown
    cleaned = clean_markdown(response_text)

    # Ensure proper sentence spacing
    cleaned = re.sub(r"([.!?])\s*([A-Z])", r"\1 \2", cleaned)

    # Remove excessive spacing
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()

    logger.debug(f"Cleaned LLM response: {len(response_text)} → {len(cleaned)} chars")

    return cleaned
