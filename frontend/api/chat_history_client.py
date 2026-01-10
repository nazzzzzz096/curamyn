import requests

API_BASE_URL = "http://localhost:8000"

def fetch_chat_history(*, token: str, session_id: str) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    r = requests.get(
        f"{API_BASE_URL}/chat/history",
        headers=headers,
        params={"session_id": session_id},
        timeout=10,
    )

    if r.status_code != 200:
        raise RuntimeError("Failed to fetch chat history")

    return r.json().get("messages", [])

def end_chat_session(token: str, session_id: str):
    headers = {"Authorization": f"Bearer {token}"}
    requests.delete(
        f"{API_BASE_URL}/chat/end-session",
        headers=headers,
        params={"session_id": session_id},
        timeout=10,
    )