import edge_tts
from typing import AsyncGenerator


async def stream_tts(text: str) -> AsyncGenerator[bytes, None]:
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-IN-NeerjaNeural",
    )

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
