from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user

def override_get_current_user():
    return {"sub": "test-user"}

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

def test_ai_interact_endpoint():
    response = client.post("http://localhost:8000/ai/interact",
                            data={
        "input_type": "text",
        "text": "Hi"
    })
    assert response.status_code == 200
