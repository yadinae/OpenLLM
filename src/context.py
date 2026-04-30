"""Context manager for OpenLLM"""

import logging
from typing import Optional
from src.enums import ContextMode
from src.history_summarizer import get_summarizer, reset_summarizer
from src.cache_awareness import get_cache_awareness, reset_cache_awareness

logger = logging.getLogger(__name__)


class ContextManager:
    """Manager for handling multi-turn context with Terse integration"""

    def __init__(self, mode: str = "dynamic", max_tokens: int = 128000, 
                 enable_summarization: bool = True, enable_cache_awareness: bool = True):
        self.mode = ContextMode(mode)
        self.max_tokens = max_tokens
        self._sessions: dict[str, list[dict]] = {}
        
        # Terse integration
        self.enable_summarization = enable_summarization
        self.enable_cache_awareness = enable_cache_awareness
        self._summarizer = get_summarizer() if enable_summarization else None
        self._cache_awareness = get_cache_awareness() if enable_cache_awareness else None

    def enhance(self, messages: list[dict], session_id: str = None) -> dict:
        """
        Enhance messages with Terse summarization and cache awareness
        
        Args:
            messages: List of message dicts
            session_id: Optional session ID for caching
        
        Returns:
            Dict with enhanced messages and metadata
        """
        result = {
            'messages': messages,
            'summarization': None,
            'cache_analysis': None,
            'original_token_count': self._estimate_tokens(messages)
        }
        
        # Apply summarization if enabled
        if self.enable_summarization and self._summarizer:
            summarization = self._summarizer.summarize(messages, self.max_tokens)
            result['messages'] = summarization.summarized_messages
            result['summarization'] = {
                'original_tokens': summarization.original_tokens,
                'summarized_tokens': summarization.summarized_tokens,
                'compression_ratio': summarization.compression_ratio,
                'summary_text': summarization.summary_text
            }
        
        # Apply cache awareness if enabled
        if self.enable_cache_awareness and self._cache_awareness:
            cache_analysis = self._cache_awareness.analyze(result['messages'])
            result['cache_analysis'] = {
                'cacheable_blocks': len(cache_analysis.cacheable_blocks),
                'potential_savings': cache_analysis.potential_savings,
                'cache_hit_rate': cache_analysis.cache_hit_rate,
                'duplicate_count': cache_analysis.duplicate_count,
                'recommendations': self._cache_awareness.get_cache_recommendations(cache_analysis)
            }
        
        # Update final token count
        result['final_token_count'] = self._estimate_tokens(result['messages'])
        result['total_compression'] = 1.0 - (result['final_token_count'] / result['original_token_count']) if result['original_token_count'] > 0 else 0.0
        
        return result

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
    
    def _estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate token count for messages"""
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            # Rough estimate: ~4 characters per token
            total += len(content) // 4 + 10  # +10 for role overhead
        return total

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
