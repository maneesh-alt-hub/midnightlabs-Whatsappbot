from collections import defaultdict, deque
from threading import Lock


class ConversationMemory:
    def __init__(self, max_turns: int = 8) -> None:
        self._messages: dict[str, deque[tuple[str, str]]] = defaultdict(
            lambda: deque(maxlen=max_turns * 2)
        )
        self._lock = Lock()

    def add_user_message(self, user_id: str, text: str) -> None:
        self._add(user_id, "User", text)

    def add_assistant_message(self, user_id: str, text: str) -> None:
        self._add(user_id, "Assistant", text)

    def get_transcript(self, user_id: str) -> str:
        with self._lock:
            messages = list(self._messages[user_id])
        return "\n".join(f"{role}: {text}" for role, text in messages)

    def _add(self, user_id: str, role: str, text: str) -> None:
        with self._lock:
            self._messages[user_id].append((role, text))
