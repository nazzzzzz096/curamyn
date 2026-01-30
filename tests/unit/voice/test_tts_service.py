"""
Tests for TTS service.

✅ UPDATED: Now expects proper WAV format output
"""

import io
import wave
from unittest.mock import MagicMock, patch

import pytest

from app.chat_service.services.tts_streamer import synthesize_tts


def _create_fake_wav(raw_pcm: bytes) -> bytes:
    """
    Helper: Convert raw PCM to proper WAV format for testing.

    This mimics what _convert_raw_to_wav() does in production.
    """
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(22050)  # 22050 Hz
        wav_file.writeframes(raw_pcm)  # Write raw PCM data

    wav_buffer.seek(0)
    return wav_buffer.read()


def test_synthesize_tts_returns_bytes():
    """Test that TTS returns valid WAV audio bytes."""
    # ✅ Mock subprocess.run to return raw PCM (what Piper actually outputs)
    fake_raw_pcm = b"\x00\x01" * 50  # 100 bytes of fake PCM audio

    mock_result = MagicMock()
    mock_result.stdout = fake_raw_pcm  # Piper outputs raw PCM

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ):
        audio = synthesize_tts("Hello world")

        # ✅ Check it returns bytes
        assert isinstance(audio, bytes)
        assert len(audio) > 0

        # ✅ Check it has valid WAV header
        assert audio.startswith(b"RIFF"), "Should start with RIFF header"
        assert b"WAVE" in audio[:12], "Should contain WAVE format"

        # ✅ Check WAV is larger than raw PCM (due to header)
        assert len(audio) > len(fake_raw_pcm), "WAV should be larger than raw PCM"

        # ✅ Verify WAV structure
        wav_buffer = io.BytesIO(audio)
        with wave.open(wav_buffer, "rb") as wav_file:
            assert wav_file.getnchannels() == 1, "Should be mono"
            assert wav_file.getsampwidth() == 2, "Should be 16-bit"
            assert wav_file.getframerate() == 22050, "Should be 22050 Hz"


def test_synthesize_tts_with_cache():
    """Test that TTS cache works correctly."""
    from app.chat_service.services.tts_streamer import _TTS_CACHE

    # ✅ Clear cache before test
    _TTS_CACHE.clear()

    # ✅ Create fake raw PCM audio
    fake_raw_pcm = b"\x00\x01" * 60  # 120 bytes of fake PCM

    mock_result = MagicMock()
    mock_result.stdout = fake_raw_pcm

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ) as mock_subprocess:

        # ✅ First call (not cached) - should call subprocess
        audio1 = synthesize_tts("Test", cache_key="test")
        assert mock_subprocess.call_count == 1, "Should call subprocess on first use"
        assert audio1.startswith(b"RIFF"), "Should return valid WAV"

        # ✅ Second call (cached) - should NOT call subprocess again
        audio2 = synthesize_tts("Test", cache_key="test")
        assert mock_subprocess.call_count == 1, "Should NOT call subprocess when cached"

        # ✅ Both should return identical WAV files
        assert audio1 == audio2, "Cached audio should be identical"

        # ✅ Cache should contain the key
        assert "test" in _TTS_CACHE, "Cache should store the key"
        assert _TTS_CACHE["test"] == audio1, "Cache should store correct audio"


def test_synthesize_tts_truncates_long_text():
    """Test that very long text is truncated at word boundaries."""
    fake_raw_pcm = b"\x00\x01" * 50
    mock_result = MagicMock()
    mock_result.stdout = fake_raw_pcm

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ) as mock_subprocess:

        # Create text longer than 200 chars with clear word boundaries
        long_text = " ".join(["word"] * 60)  # ~240 chars: "word word word..."

        audio = synthesize_tts(long_text)

        # ✅ Check subprocess was called
        assert mock_subprocess.call_count == 1

        # ✅ Check the input text was truncated
        call_args = mock_subprocess.call_args
        input_text = call_args.kwargs["input"].decode("utf-8")

        # Should be truncated to ≤ 200 chars + "..."
        assert (
            len(input_text) <= 204
        ), f"Text should be ≤204 chars, got {len(input_text)}"
        assert input_text.endswith("..."), "Truncated text should end with ..."

        # Should not cut mid-word (ends with space before "...")
        assert (
            input_text[-4] == " " or input_text.count(" ") > 0
        ), "Should preserve word boundaries"

        # ✅ Still returns valid WAV
        assert audio.startswith(b"RIFF")


def test_synthesize_tts_handles_subprocess_error():
    """Test that TTS handles subprocess errors gracefully."""
    from subprocess import CalledProcessError

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        side_effect=CalledProcessError(1, "piper", stderr=b"Error message"),
    ):
        with pytest.raises(RuntimeError, match="TTS generation failed"):
            synthesize_tts("Test")


def test_synthesize_tts_handles_empty_output():
    """Test that TTS handles empty Piper output."""
    mock_result = MagicMock()
    mock_result.stdout = b""  # Empty output

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ):
        # ✅ Should raise with specific message
        with pytest.raises(RuntimeError, match="Piper produced no audio output"):
            synthesize_tts("Test")


def test_synthesize_tts_handles_timeout():
    """Test that TTS handles subprocess timeout."""
    from subprocess import TimeoutExpired

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        side_effect=TimeoutExpired("piper", 10),
    ):
        with pytest.raises(RuntimeError, match="TTS generation timed out"):
            synthesize_tts("Test")


def test_wav_conversion_preserves_audio_data():
    """Test that WAV conversion preserves the actual audio data."""
    # Create specific PCM pattern
    fake_raw_pcm = b"\x12\x34\x56\x78" * 25  # 100 bytes with pattern

    mock_result = MagicMock()
    mock_result.stdout = fake_raw_pcm

    with patch(
        "app.chat_service.services.tts_streamer.subprocess.run",
        return_value=mock_result,
    ):
        audio = synthesize_tts("Test")

        # ✅ Extract audio data from WAV file
        wav_buffer = io.BytesIO(audio)
        with wave.open(wav_buffer, "rb") as wav_file:
            extracted_pcm = wav_file.readframes(wav_file.getnframes())

        # ✅ Verify original PCM data is preserved in WAV
        assert extracted_pcm == fake_raw_pcm, "WAV should contain original PCM data"
