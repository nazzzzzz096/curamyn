"""
Memory API client.

Handles user memory deletion from frontend.
"""

import requests
from frontend.state.app_state import state

API_BASE_URL = "http://localhost:8000"


def delete_memory() -> dict:
    """
    Delete all stored user memory from backend.

    Raises:
        RuntimeError: If deletion fails
    """
    if not state.token:
        raise RuntimeError("User not authenticated")

    response = requests.delete(
        f"{API_BASE_URL}/memory/clear",  
        headers={
            "Authorization": f"Bearer {state.token}",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if response.status_code != 200:
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text

        raise RuntimeError(detail or "Failed to delete memory")

    return response.json()
