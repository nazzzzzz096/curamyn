from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user


def override_user():
    return {"sub": "test-user"}


app.dependency_overrides[get_current_user] = override_user

client = TestClient(app)


def test_clear_memory():
    response = client.delete("/memory/clear")
    assert response.status_code == 200
    assert "deleted_sessions" in response.json()
