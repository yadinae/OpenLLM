"""Context manager for OpenLLM"""

import logging
from typing import Optional
from src.enums import ContextMode

logger = logging.getLogger(__name__)


class ContextManager:
    """Manager for handling multi-turn context"""

    def __init__(self, mode: str = "dynamic", max_tokens: int = 128000):
        self.mode = ContextMode(mode)
        self.max_tokens = max_tokens
        self._sessions: dict[str, list[dict]] = {}

    def prune(
        self, messages: list[dict], mode: Optional[str] = None, max_tokens: Optional[int] = None
    ) -> list[dict]:
        mode = mode or self.mode.value
        max_tokens = max_tokens or self.max_tokens

        if mode == "static":
            return self._prune_static(messages, max_tokens)
        elif mode == "dynamic":
            return self._prune_dynamic(messages, max_tokens)
        elif mode == "reservoir":
            return self._prune_reservoir(messages, max_tokens)
        elif mode == "adaptive":
            return self._prune_adaptive(messages, max_tokens)
        else:
            return messages

    def _prune_static(self, messages: list[dict], max_tokens: int) -> list[dict]:
        return messages[-10:]

    def _prune_dynamic(self, messages: list[dict], max_tokens: int) -> list[dict]:
        estimated_tokens = sum(len(m.get("content", "").split()) for m in messages)

        if estimated_tokens <= max_tokens:
            return messages

        result = []
        current_tokens = 0

        for msg in reversed(messages):
            msg_tokens = len(msg.get("content", "").split())
            if current_tokens + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            current_tokens += msg_tokens

        return result

    def _prune_reservoir(self, messages: list[dict], max_tokens: int) -> list[dict]:
        if len(messages) <= 4:
            return messages

        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

        recent = []
        if system_msgs:
            recent.append(system_msgs[-1])

        if user_msgs:
            recent.append(user_msgs[-1])
        if assistant_msgs:
            recent.append(assistant_msgs[-1])

        history = []
        for i, msg in enumerate(messages[:-2]):
            if len(history) >= 4:
                break
            history.append(msg)

        return history + recent

    def _prune_adaptive(self, messages: list[dict], max_tokens: int) -> list[dict]:
        last_msg = messages[-1].get("content", "").lower() if messages else ""

        is_coding = any(
            kw in last_msg
            for kw in ["code", "function", "class", "def ", "import", "write", "implement"]
        )

        if is_coding:
            return self._prune_static(messages, max_tokens)
        else:
            return self._prune_dynamic(messages, max_tokens)

    def get_session(self, session_id: str) -> Optional[list[dict]]:
        return self._sessions.get(session_id)

    def set_session(self, session_id: str, messages: list[dict]):
        self._sessions[session_id] = messages

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]


_default_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get global context manager"""
    global _default_context_manager
    if _default_context_manager is None:
        _default_context_manager = ContextManager()
    return _default_context_manager
