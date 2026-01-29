"""
Tests for TTS service.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.chat_service.services.tts_streamer import synthesize_tts


def test_synthesize_tts_returns_bytes():
    """Test that TTS returns audio bytes."""

    # Mock subprocess.run to return fake audio data
    fake_audio = b"RIFF" + b"\x00" * 100  # Fake WAV header + data

    mock_result = MagicMock()
    mock_result.stdout = fake_audio

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ):
        audio = synthesize_tts("Hello world")

        assert isinstance(audio, bytes)
        assert len(audio) > 0
        assert audio == fake_audio


def test_synthesize_tts_with_cache():
    """Test that TTS cache works."""

    # ✅ FIX: Clear cache and manually populate it
    from app.chat_service.services.tts_streamer import _TTS_CACHE

    _TTS_CACHE.clear()  # Start fresh

    fake_audio = b"CACHED_AUDIO" * 10
    mock_result = MagicMock()
    mock_result.stdout = fake_audio

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ) as mock_subprocess:

        # ✅ First call (not cached) - should call subprocess
        audio1 = synthesize_tts("Test", cache_key="test")
        assert audio1 == fake_audio
        assert mock_subprocess.call_count == 1

        # ✅ Manually verify cache was populated
        assert "test" in _TTS_CACHE
        assert _TTS_CACHE["test"] == fake_audio

        # ✅ Second call (should use cache) - should NOT call subprocess
        audio2 = synthesize_tts("Different text", cache_key="test")
        assert audio2 == fake_audio
        assert mock_subprocess.call_count == 1  # Still 1, not 2!


def test_synthesize_tts_limits_length():
    """Test that TTS limits text length."""

    fake_audio = b"SHORT_AUDIO"
    mock_result = MagicMock()
    mock_result.stdout = fake_audio

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ) as mock_subprocess:

        # Very long text
        long_text = "Hello " * 100  # 600+ chars

        audio = synthesize_tts(long_text)

        # Check that the text was truncated
        call_args = mock_subprocess.call_args
        input_text = call_args[1]["input"].decode("utf-8")

        assert len(input_text) <= 210  # Should be truncated to ~200 chars + "..."
        assert "..." in input_text


def test_synthesize_tts_handles_errors():
    """Test that TTS handles subprocess errors gracefully."""

    import subprocess

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "piper", stderr=b"Error"),
    ):

        with pytest.raises(RuntimeError, match="TTS generation failed"):
            synthesize_tts("Test text")


def test_init_tts_cache():
    """Test that TTS cache initialization works."""

    from app.chat_service.services.tts_streamer import init_tts_cache, _TTS_CACHE

    fake_audio = b"CACHED"
    mock_result = MagicMock()
    mock_result.stdout = fake_audio

    # Clear cache first
    _TTS_CACHE.clear()

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ):
        init_tts_cache()

        # Check that cache was populated
        assert len(_TTS_CACHE) > 0
        assert "hello" in _TTS_CACHE
        assert "error" in _TTS_CACHE
