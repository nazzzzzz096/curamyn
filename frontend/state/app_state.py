from typing import Optional, Dict, List


class AppState:
    token: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # ✅ CONSENT IS A DICT NOW
    consent: Dict[str, bool] = {
        "memory": False,
        "voice": False,
        "document": False,
        "image": False,
    }

    # Chat history
    messages: List[dict] = []


state = AppState()
