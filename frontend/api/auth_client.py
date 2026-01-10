"""
Authentication API client for frontend.

Handles communication with backend auth endpoints.
"""

import requests
from frontend.config import settings

BACKEND_BASE_URL = "http://127.0.0.1:8000"


def login_user(email: str, password: str) -> dict:
    """
    Authenticate user via backend API.

    Args:
        email (str): User email
        password (str): User password

    Returns:
        dict: JSON response containing access token

    Raises:
        RuntimeError: On authentication failure
    """
    response = requests.post(
        f"{BACKEND_BASE_URL}/auth/login",
        json={
            "email": email,
            "password": password,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            response.json().get("detail", "Login failed")
        )

    return response.json()


def signup_user(email: str, password: str) -> dict:
    """
    Register new user via backend API.

    Args:
        email (str): User email
        password (str): User password

    Returns:
        dict: Created user payload

    Raises:
        RuntimeError: On signup failure
    """
    response = requests.post(
        f"{BACKEND_BASE_URL}/auth/signup",
        json={
            "email": email,
            "password": password,
        },
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            response.json().get("detail", "Signup failed")
        )

    return response.json()



def logout_user(token: str, session_id: str | None = None):
    params = {}
    if session_id:
        params["session_id"] = session_id

    response = requests.post(
        f"{BACKEND_BASE_URL}/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(response.json().get("detail", "Logout failed"))
