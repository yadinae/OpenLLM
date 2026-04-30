"""
History Summarizer for OpenLLM

Automatically summarizes long conversation history to reduce token usage
while preserving key information and context continuity.

Strategies:
- Extractive: Select key sentences from original messages
- Abstractive: Generate concise summary of conversation flow
- Hybrid: Combine both approaches for optimal results
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SummarizationResult:
    """Result of history summarization"""
    original_messages: list
    summarized_messages: list
    original_tokens: int
    summarized_tokens: int
    compression_ratio: float
    summary_text: str = ""


class HistorySummarizer:
    """
    Automatically summarizes long conversation history to reduce token usage.
    
    Features:
    - Configurable token thresholds
    - Multiple summarization strategies
    - Preserves system prompts and recent messages
    - Extracts key actions and conclusions
    """
    
    # Key action indicators
    ACTION_PATTERNS = [
        r'(?:create|build|implement|design|fix|debug|optimize|refactor|deploy)\s+(?:a|an|the)?\s*(\w+)',
        r'(?:write|generate|produce)\s+(?:a|an|the)?\s*(\w+)\s+(?:code|function|class|method)',
        r'(?:add|remove|update|modify)\s+(?:the)?\s*(\w+)',
        r'(?:analyze|review|examine)\s+(?:the)?\s*(\w+)',
        r'(?:test|verify|validate)\s+(?:the)?\s*(\w+)',
    ]
    
    # Conclusion indicators
    CONCLUSION_PATTERNS = [
        r'(?:therefore|thus|consequently|as a result|in conclusion)\s+(.+?)[.!]',
        r'(?:the|this)\s+(?:solution|approach|method)\s+(?:is|uses|provides)\s+(.+?)[.!]',
        r'(?:successfully|completed|finished)\s+(.+?)[.!]',
        r'(?:error|issue|problem)\s+(?:was|is)\s+(?:resolved|fixed|solved)\s+(.+?)[.!]',
    ]
    
    # Technical term patterns
    TECHNICAL_PATTERN = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b\w+(?:ing|tion|ment|ness)\b')
    
    def __init__(self, config: dict = None):
        """
        Initialize HistorySummarizer
        
        Args:
            config: Optional configuration dict
                - max_tokens_before_summarize: Token count threshold to trigger summarization
                - recent_messages_to_keep: Number of recent messages to preserve
                - summary_max_tokens: Maximum tokens for summary
                - strategy: Summarization strategy ('extractive', 'abstractive', 'hybrid')
        """
        self.config = config or {}
        self.max_tokens_before_summarize = self.config.get('max_tokens_before_summarize', 4000)
        self.recent_messages_to_keep = self.config.get('recent_messages_to_keep', 4)
        self.summary_max_tokens = self.config.get('summary_max_tokens', 500)
        self.strategy = self.config.get('strategy', 'hybrid')
    
    def summarize(self, messages: list, max_tokens: int = None) -> SummarizationResult:
        """
        Summarize conversation history if it exceeds token threshold
        
        Args:
            messages: List of message dicts (role, content)
            max_tokens: Optional override for max token threshold
        
        Returns:
            SummarizationResult with original and summarized messages
        """
        max_tok = max_tokens or self.max_tokens_before_summarize
        
        # Estimate token count
        original_tokens = self._estimate_tokens(messages)
        
        # Check if summarization is needed
        if original_tokens <= max_tok:
            return SummarizationResult(
                original_messages=messages,
                summarized_messages=messages,
                original_tokens=original_tokens,
                summarized_tokens=original_tokens,
                compression_ratio=0.0,
                summary_text=""
            )
        
        # Split messages into recent and old
        recent_messages = messages[-self.recent_messages_to_keep:]
        old_messages = messages[:-self.recent_messages_to_keep]
        
        if not old_messages:
            return SummarizationResult(
                original_messages=messages,
                summarized_messages=messages,
                original_tokens=original_tokens,
                summarized_tokens=original_tokens,
                compression_ratio=0.0,
                summary_text=""
            )
        
        # Generate summary of old messages
        summary_text = self._generate_summary(old_messages)
        
        # Create summarized message list
        summarized_messages = []
        
        # Keep system prompts
        system_msgs = [m for m in old_messages if m.get('role') == 'system']
        if system_msgs:
            summarized_messages.append(system_msgs[-1])
        
        # Add summary
        summarized_messages.append({
            'role': 'system',
            'content': f'[Earlier conversation summarized]: {summary_text}'
        })
        
        # Add recent messages
        summarized_messages.extend(recent_messages)
        
        # Estimate new token count
        summarized_tokens = self._estimate_tokens(summarized_messages)
        
        # Calculate compression ratio
        compression_ratio = 1.0 - (summarized_tokens / original_tokens) if original_tokens > 0 else 0.0
        
        return SummarizationResult(
            original_messages=messages,
            summarized_messages=summarized_messages,
            original_tokens=original_tokens,
            summarized_tokens=summarized_tokens,
            compression_ratio=compression_ratio,
            summary_text=summary_text
        )
    
    def _estimate_tokens(self, messages: list) -> int:
        """Estimate token count for messages"""
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            # Rough estimate: ~4 characters per token
            total += len(content) // 4 + 10  # +10 for role overhead
        return total
    
    def _generate_summary(self, messages: list) -> str:
        """
        Generate summary based on configured strategy
        
        Args:
            messages: Messages to summarize
        
        Returns:
            Summary text
        """
        if self.strategy == 'extractive':
            return self._extractive_summary(messages)
        elif self.strategy == 'abstractive':
            return self._abstractive_summary(messages)
        else:
            return self._hybrid_summary(messages)
    
    def _extractive_summary(self, messages: list) -> str:
        """Extract key sentences from messages"""
        user_msgs = [m for m in messages if m.get('role') == 'user']
        assistant_msgs = [m for m in messages if m.get('role') == 'assistant']
        
        summary_parts = []
        
        # Extract first few key exchanges
        for i, (user, assistant) in enumerate(zip(user_msgs[:5], assistant_msgs[:5])):
            user_content = user.get('content', '')
            assistant_content = assistant.get('content', '')
            
            # Extract key actions from user message
            user_actions = self._extract_key_actions(user_content)
            
            # Extract key conclusions from assistant message
            assistant_conclusions = self._extract_key_conclusions(assistant_content)
            
            if user_actions or assistant_conclusions:
                part = f"User: {user_actions or 'asked question'}"
                if assistant_conclusions:
                    part += f" → Assistant: {assistant_conclusions}"
                summary_parts.append(part)
        
        return ' | '.join(summary_parts)
    
    def _abstractive_summary(self, messages: list) -> str:
        """Generate abstractive summary (simplified)"""
        user_msgs = [m for m in messages if m.get('role') == 'user']
        assistant_msgs = [m for m in messages if m.get('role') == 'assistant']
        
        if not user_msgs:
            return "No user messages in history"
        
        # Extract topics from user messages
        topics = []
        for msg in user_msgs[:3]:
            content = msg.get('content', '')
            # Extract first sentence or key phrase
            first_sentence = content.split('.')[0][:100]
            topics.append(first_sentence)
        
        # Count technical terms
        all_content = ' '.join(m.get('content', '') for m in messages)
        technical_terms = self.TECHNICAL_PATTERN.findall(all_content)
        unique_terms = list(set(technical_terms))[:5]
        
        summary = f"Conversation covered: {', '.join(topics[:2])}."
        if unique_terms:
            summary += f" Key topics: {', '.join(unique_terms)}."
        
        return summary
    
    def _hybrid_summary(self, messages: list) -> str:
        """Combine extractive and abstractive approaches"""
        user_msgs = [m for m in messages if m.get('role') == 'user']
        assistant_msgs = [m for m in messages if m.get('role') == 'assistant']
        
        if not user_msgs:
            return "No user messages in history"
        
        summary_parts = []
        
        # Extractive: Get key exchanges
        for i, (user, assistant) in enumerate(zip(user_msgs[:3], assistant_msgs[:3])):
            user_content = user.get('content', '')
            assistant_content = assistant.get('content', '')
            
            # Get first meaningful sentence
            user_key = self._get_first_sentence(user_content)
            assistant_key = self._get_first_sentence(assistant_content)
            
            if user_key:
                part = f"User requested: {user_key}"
                if assistant_key:
                    part += f"; Assistant responded: {assistant_key}"
                summary_parts.append(part)
        
        # Abstractive: Add topic overview
        all_content = ' '.join(m.get('content', '') for m in messages[:4])
        words = all_content.split()
        if len(words) > 20:
            topic_words = [w for w in words if len(w) > 4][:5]
            if topic_words:
                summary_parts.append(f"Topics: {', '.join(topic_words)}")
        
        return '. '.join(summary_parts[:2]) + '.'
    
    def _extract_key_actions(self, content: str) -> str:
        """Extract key actions from user message"""
        content_lower = content.lower()
        
        for pattern in self.ACTION_PATTERNS:
            match = re.search(pattern, content_lower)
            if match:
                return match.group(0)[:80]
        
        # Fallback: first sentence
        return self._get_first_sentence(content)
    
    def _extract_key_conclusions(self, content: str) -> str:
        """Extract key conclusions from assistant message"""
        for pattern in self.CONCLUSION_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)[:80]
        
        # Fallback: first sentence
        return self._get_first_sentence(content)
    
    def _get_first_sentence(self, content: str) -> str:
        """Get first sentence of content"""
        if not content:
            return ""
        
        # Remove code blocks for summary
        clean_content = re.sub(r'```[\s\S]*?```', '[code]', content)
        
        # Get first sentence
        sentences = re.split(r'[.!?]', clean_content)
        if sentences:
            first = sentences[0].strip()
            return first[:100] if len(first) > 100 else first
        
        return content[:100]


# Global summarizer instance
_summarizer: Optional[HistorySummarizer] = None


def get_summarizer(config: dict = None) -> HistorySummarizer:
    """Get or create global HistorySummarizer instance"""
    global _summarizer
    if _summarizer is None:
        _summarizer = HistorySummarizer(config)
    return _summarizer


def reset_summarizer():
    """Reset global summarizer (for testing)"""
    global _summarizer
    _summarizer = None
