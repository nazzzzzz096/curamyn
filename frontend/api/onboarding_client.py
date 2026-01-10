import requests

BASE_URL = "http://localhost:8000"


def get_next_question(token: str) -> dict:
    response = requests.get(
        f"{BASE_URL}/questions/next",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def submit_answer(token: str, question_key: str, answer: str | None) -> dict:
    response = requests.post(
        f"{BASE_URL}/questions/answer",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "question_key": question_key,
            "answer": answer,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
