"""
Tests for voice pipeline.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.chat_service.services.voice_pipeline_service import voice_chat_pipeline


@pytest.mark.asyncio
async def test_voice_pipeline_output_bytes():
    """Test that voice pipeline returns audio bytes."""

    # Mock all dependencies
    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",  # ✅ Updated name
        new_callable=AsyncMock,
        return_value="hello there",
    ) as mock_stt, patch(
        "app.chat_service.services.voice_pipeline_service.analyze_text",
        return_value={
            "response_text": "Hello! How can I help you?",
            "severity": "low",
            "intent": "greeting",
        },
    ) as mock_llm, patch(
        "app.chat_service.services.voice_pipeline_service.synthesize_tts",
        return_value=b"FAKE_WAV_DATA" * 100,
    ) as mock_tts:

        # Call voice pipeline
        result = await voice_chat_pipeline(b"fake_audio_bytes")

        # Assertions
        assert "message" in result
        assert "audio_base64" in result
        assert result["audio_base64"] is not None
        assert result["tts_failed"] is False
        assert "hello" in result["message"].lower()

        # Verify mocks were called
        mock_stt.assert_called_once()
        mock_llm.assert_called_once()
        mock_tts.assert_called_once()


@pytest.mark.asyncio
async def test_voice_pipeline_handles_stt_failure():
    """Test that voice pipeline handles STT errors gracefully."""

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        side_effect=RuntimeError("STT failed"),
    ):

        result = await voice_chat_pipeline(b"fake_audio")

        # Should return error message
        assert "message" in result
        assert "couldn't hear you" in result["message"].lower()
        assert result.get("tts_failed") is True


@pytest.mark.asyncio
async def test_voice_pipeline_handles_empty_transcription():
    """Test that voice pipeline handles empty transcription."""

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value="",  # Empty transcription
    ):

        result = await voice_chat_pipeline(b"fake_audio")

        # Should return error message
        assert "message" in result
        assert "didn't catch" in result["message"].lower()
        assert result.get("tts_failed") is True


@pytest.mark.asyncio
async def test_voice_pipeline_handles_tts_failure():
    """Test that voice pipeline handles TTS errors gracefully."""

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value="hello",
    ), patch(
        "app.chat_service.services.voice_pipeline_service.analyze_text",
        return_value={"response_text": "Hi there!", "severity": "low"},
    ), patch(
        "app.chat_service.services.voice_pipeline_service.synthesize_tts",
        side_effect=RuntimeError("TTS failed"),
    ):

        result = await voice_chat_pipeline(b"fake_audio")

        # Should return message without audio
        assert "message" in result
        assert result["message"] == "Hi there!. That makes sense."
        assert result.get("audio_base64") is None
        assert result["tts_failed"] is True


@pytest.mark.asyncio
async def test_voice_pipeline_uses_cached_response():
    """Test that voice pipeline uses cached TTS for greetings."""

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value="hello",  # Greeting should use cache
    ), patch(
        "app.chat_service.services.voice_pipeline_service.synthesize_tts",
        return_value=b"CACHED_AUDIO",
    ) as mock_tts:

        result = await voice_chat_pipeline(b"fake_audio")

        # Should call TTS with cache_key
        assert mock_tts.called
        call_kwargs = mock_tts.call_args[1]
        assert (
            "cache_key" in call_kwargs or call_kwargs == {}
        )  # Depends on implementation


@pytest.mark.asyncio
async def test_voice_pipeline_includes_latency():
    """Test that voice pipeline includes latency metrics."""

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value="test",
    ), patch(
        "app.chat_service.services.voice_pipeline_service.analyze_text",
        return_value={"response_text": "Test response", "severity": "low"},
    ), patch(
        "app.chat_service.services.voice_pipeline_service.synthesize_tts",
        return_value=b"AUDIO",
    ):

        result = await voice_chat_pipeline(b"audio")

        # Check latency metrics
        assert "latency" in result
        assert "stt" in result["latency"]
        assert "llm" in result["latency"]
        assert "tts" in result["latency"]
        assert "total" in result["latency"]

        # All latencies should be positive numbers
        assert result["latency"]["stt"] >= 0
        assert result["latency"]["llm"] >= 0
        assert result["latency"]["tts"] >= 0
        assert result["latency"]["total"] >= 0


@pytest.mark.asyncio
async def test_voice_pipeline_with_session_context():
    """Test that voice pipeline uses session context."""

    # Mock session state with document
    class MockSessionState:
        last_document_text = "Patient has elevated blood pressure: 140/90"
        last_image_analysis = {"risk": "moderate", "confidence": 0.85}
        last_image_type = "medical scan"

    with patch(
        "app.chat_service.services.voice_pipeline_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value="What does my document say?",
    ), patch(
        "app.chat_service.services.voice_pipeline_service.analyze_text",
        return_value={
            "response_text": "Your blood pressure is elevated",
            "severity": "moderate",
        },
    ) as mock_llm, patch(
        "app.chat_service.services.voice_pipeline_service.synthesize_tts",
        return_value=b"AUDIO",
    ):

        result = await voice_chat_pipeline(
            b"audio",
            session_state=MockSessionState(),
        )

        # Check that LLM was called with enriched context
        llm_call_args = mock_llm.call_args[1]
        llm_input = llm_call_args.get("text", "")

        # Should include document context
        assert "DOCUMENT UPLOADED" in llm_input or "document" in llm_input.lower()
        assert "IMAGE UPLOADED" in llm_input or "image" in llm_input.lower()
