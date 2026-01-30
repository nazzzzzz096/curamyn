"""
Test if backend TTS generates VALID audio files.
"""

import os
import base64
import requests
from pathlib import Path
import subprocess

BACKEND_URL = "http://localhost:8000"


def test_voice_pipeline():
    """Test the full voice pipeline."""

    print("🧪 Testing Curamyn Voice Pipeline...")
    print("-" * 50)

    # Step 1: Login
    print("\n1️⃣ Logging in...")
    login_response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={
            "email": "nazina096@gmail.com",  # ✅ Your email
            "password": "nazi123",  # ✅ Your password
        },
    )

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    print(f"✅ Login successful!")

    # Step 2: Create fake audio
    print("\n2️⃣ Creating fake audio input...")
    fake_audio = b"fake_audio_data" * 100

    # Step 3: Send to voice pipeline
    print("\n3️⃣ Sending to /ai/interact endpoint...")

    files = {"audio": ("test.webm", fake_audio, "audio/webm")}

    data = {
        "input_type": "audio",
        "response_mode": "voice",
    }

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{BACKEND_URL}/ai/interact",
        files=files,
        data=data,
        headers=headers,
        timeout=60,
    )

    print(f"\n📊 Response Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()

        print("\n✅ Backend Response:")
        print(f"   - Message: {result.get('message', 'N/A')[:50]}...")
        print(f"   - TTS Failed: {result.get('tts_failed', 'N/A')}")
        print(f"   - Has Audio: {bool(result.get('audio_base64'))}")

        # Save and validate audio
        if result.get("audio_base64"):
            audio_data = base64.b64decode(result["audio_base64"])
            output_file = Path("test_output.wav")
            output_file.write_bytes(audio_data)

            print(f"\n💾 Audio saved to: {output_file.absolute()}")
            print(f"   File size: {len(audio_data)} bytes")

            # ✅ VALIDATE WAV FILE
            print("\n🔍 Validating WAV file...")

            # Check WAV header
            if audio_data.startswith(b"RIFF") and b"WAVE" in audio_data[:12]:
                print("   ✅ Valid WAV header detected!")
            else:
                print("   ❌ Invalid WAV header!")
                print(f"   First 12 bytes: {audio_data[:12]}")
                return

            # Try to get file info with ffprobe
            try:
                result = subprocess.run(
                    ["ffprobe", "-i", str(output_file), "-hide_banner"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if "Audio:" in result.stderr:
                    print("   ✅ Audio stream detected by ffprobe!")

                    # Extract details
                    for line in result.stderr.split("\n"):
                        if "Audio:" in line or "Duration:" in line:
                            print(f"   {line.strip()}")
                else:
                    print("   ⚠️ No audio stream found")

            except FileNotFoundError:
                print("   ℹ️ ffprobe not found (install ffmpeg to validate)")
            except Exception as e:
                print(f"   ⚠️ Could not validate: {e}")

            # Try to play
            print("\n🎵 Try playing with:")
            print(f"   ffplay {output_file}")
            print(f"   vlc {output_file}")

        else:
            print("\n⚠️ No audio in response")
    else:
        print(f"\n❌ FAILED: {response.text}")


if __name__ == "__main__":
    test_voice_pipeline()
