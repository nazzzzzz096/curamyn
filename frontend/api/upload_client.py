import requests
from typing import Optional

API_BASE_URL = "http://localhost:8000"

def send_ai_interaction(
    *,
    token: str,
    input_type: str,
    session_id: str | None = None,
    text: Optional[str] = None,
    image_type: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
):
    headers = {
        "Authorization": f"Bearer {token}",
    }

    # These go as standard form-data fields
    data = {
        "input_type": input_type,
        "response_mode": "text",
        "session_id": session_id,  # Added to match your Swagger screenshot
    } 

    if text:
        data["text"] = text
    if image_type:
        data["image_type"] = image_type

    files = None
    if file_bytes:
        # IMPORTANT: The key "image" must match the name in your FastAPI UploadFile parameter
        files = {
            "image": ("upload.png", file_bytes, "image/png"),
        }

    response = requests.post(
        f"{API_BASE_URL}/ai/interact",
        headers=headers,
        data=data,
        files=files,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Backend Error ({response.status_code}): {response.text}")

    return response.json()