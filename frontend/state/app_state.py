from typing import Optional, Dict, List


class AppState:
    token: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # Consent flags
    consent: Dict[str, bool] = {
        "memory": False,
        "voice": False,
        "document": False,
        "image": False,
    }

    # Chat history
    messages: List[dict] = []

    #  UI / FLOW STATE
    logging_in: bool = False


state = AppState()
