from piper import PiperVoice
import wave

MODEL_PATH = "models/en_US-amy-low.onnx"
OUTPUT_WAV = "piper_test.wav"
TEXT = "Hello. This is a test of Piper text to speech."


def main():
    print("Loading Piper model...")
    voice = PiperVoice.load(MODEL_PATH)

    print("Generating audio...")
    audio_bytes = b""
    sample_rate = 22050
    channels = 1
    sample_width = 2  # 16-bit

    for chunk in voice.synthesize(TEXT):
        audio_bytes += chunk.audio_int16_bytes
        sample_rate = chunk.sample_rate
        channels = chunk.sample_channels
        sample_width = chunk.sample_width

    print("Writing WAV file...")
    with wave.open(OUTPUT_WAV, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)

    print(f"✅ Done! Saved as {OUTPUT_WAV}")


if __name__ == "__main__":
    main()
