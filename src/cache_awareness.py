"""
Cache Awareness for OpenLLM

Detects cacheable content blocks in messages to optimize API calls
by identifying repeated content, system prompts, and structured data.

Features:
- Content hash-based duplicate detection
- System prompt caching
- Code block caching
- Cache priority scoring
"""

import hashlib
import re
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheBlock:
    """A cacheable content block"""
    index: int
    content: str
    block_type: str  # 'system_prompt', 'code_block', 'repeated_content', 'structured_data'
    cache_priority: str  # 'high', 'medium', 'low'
    content_hash: str = ""
    estimated_tokens: int = 0
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()[:12]
        self.estimated_tokens = len(self.content) // 4


@dataclass
class CacheAnalysis:
    """Result of cache analysis"""
    cacheable_blocks: list = field(default_factory=list)
    potential_savings: int = 0
    cache_hit_rate: float = 0.0
    total_blocks: int = 0
    duplicate_count: int = 0


class CacheAwareness:
    """
    Detects cacheable content blocks in messages.
    
    Features:
    - Identifies system prompts for caching
    - Detects duplicate content across messages
    - Recognizes code blocks as cacheable
    - Scores cache priority
    """
    
    # System prompt indicators
    SYSTEM_PATTERNS = [
        r'you are (?:a|an)\s+\w+',
        r'you should\s+',
        r'you must\s+',
        r'always\s+',
        r'never\s+',
        r'follow these rules',
        r'remember that',
        r'important:',
        r'note:',
    ]
    
    # Code block patterns
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')
    INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
    
    # Structured data patterns
    STRUCTURED_PATTERNS = [
        r'\{[^{}]+\}',  # JSON-like
        r'<\w+>.*?</\w+>',  # XML-like
        r'\|\s*\w+\s*\|',  # Markdown tables
        r'^\d+\.\s+',  # Numbered lists
        r'^[-*]\s+',  # Bullet lists
    ]
    
    def __init__(self, config: dict = None):
        """
        Initialize CacheAwareness
        
        Args:
            config: Optional configuration dict
                - min_block_size: Minimum content size to consider for caching
                - cache_registry: Optional existing cache registry
        """
        self.config = config or {}
        self.min_block_size = self.config.get('min_block_size', 50)
        self.cache_registry: dict[str, int] = {}  # content_hash → first occurrence index
    
    def analyze(self, messages: list) -> CacheAnalysis:
        """
        Analyze messages for cacheable content
        
        Args:
            messages: List of message dicts
        
        Returns:
            CacheAnalysis with cacheable blocks and statistics
        """
        cacheable_blocks = []
        duplicate_count = 0
        total_potential_savings = 0
        
        for i, msg in enumerate(messages):
            content = msg.get('content', '')
            role = msg.get('role', '')
            
            # Skip empty or short messages
            if len(content) < self.min_block_size:
                continue
            
            # Check for system prompts
            if role == 'system':
                priority = self._score_system_prompt(content)
                if priority:
                    cacheable_blocks.append(CacheBlock(
                        index=i,
                        content=content,
                        block_type='system_prompt',
                        cache_priority=priority
                    ))
                    continue
            
            # Check for code blocks
            code_blocks = self.CODE_BLOCK_PATTERN.findall(content)
            if code_blocks:
                for code in code_blocks:
                    if len(code) >= self.min_block_size:
                        cacheable_blocks.append(CacheBlock(
                            index=i,
                            content=code,
                            block_type='code_block',
                            cache_priority='high'
                        ))
                continue
            
            # Check for duplicate content
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in self.cache_registry:
                duplicate_count += 1
                block = CacheBlock(
                    index=i,
                    content=content,
                    block_type='repeated_content',
                    cache_priority='medium',
                    content_hash=content_hash[:12]
                )
                cacheable_blocks.append(block)
                total_potential_savings += block.estimated_tokens
            else:
                self.cache_registry[content_hash] = i
            
            # Check for structured data
            if self._is_structured_data(content):
                cacheable_blocks.append(CacheBlock(
                    index=i,
                    content=content,
                    block_type='structured_data',
                    cache_priority='low'
                ))
        
        # Calculate statistics
        total_blocks = len(messages)
        cache_hit_rate = duplicate_count / total_blocks if total_blocks > 0 else 0.0
        
        # Add savings from high-priority blocks
        for block in cacheable_blocks:
            if block.cache_priority == 'high':
                total_potential_savings += block.estimated_tokens * 0.8  # 80% savings estimate
        
        return CacheAnalysis(
            cacheable_blocks=cacheable_blocks,
            potential_savings=total_potential_savings,
            cache_hit_rate=cache_hit_rate,
            total_blocks=total_blocks,
            duplicate_count=duplicate_count
        )
    
    def _score_system_prompt(self, content: str) -> Optional[str]:
        """Score system prompt for cache priority"""
        score = 0
        
        # Check for system prompt indicators
        for pattern in self.SYSTEM_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score += 1
        
        # Length factor
        if len(content) > 200:
            score += 2
        elif len(content) > 100:
            score += 1
        
        # Determine priority
        if score >= 3:
            return 'high'
        elif score >= 1:
            return 'medium'
        else:
            return None
    
    def _is_structured_data(self, content: str) -> bool:
        """Check if content contains structured data"""
        structured_count = 0
        
        for pattern in self.STRUCTURED_PATTERNS:
            if re.search(pattern, content, re.MULTILINE):
                structured_count += 1
        
        return structured_count >= 2
    
    def get_cache_recommendations(self, analysis: CacheAnalysis) -> list:
        """
        Get caching recommendations based on analysis
        
        Args:
            analysis: Cache analysis result
        
        Returns:
            List of recommendation dicts
        """
        recommendations = []
        
        # System prompt recommendations
        system_blocks = [b for b in analysis.cacheable_blocks if b.block_type == 'system_prompt']
        if system_blocks:
            recommendations.append({
                'type': 'cache_system_prompt',
                'priority': 'high',
                'message': f'Found {len(system_blocks)} system prompt(s) - cache for all requests',
                'estimated_savings': sum(b.estimated_tokens for b in system_blocks)
            })
        
        # Code block recommendations
        code_blocks = [b for b in analysis.cacheable_blocks if b.block_type == 'code_block']
        if code_blocks:
            recommendations.append({
                'type': 'cache_code_blocks',
                'priority': 'medium',
                'message': f'Found {len(code_blocks)} code block(s) - cache during editing sessions',
                'estimated_savings': sum(b.estimated_tokens for b in code_blocks)
            })
        
        # Duplicate content recommendations
        if analysis.duplicate_count > 0:
            recommendations.append({
                'type': 'deduplicate_content',
                'priority': 'medium',
                'message': f'Found {analysis.duplicate_count} duplicate message(s) - remove or reference',
                'estimated_savings': analysis.potential_savings
            })
        
        # Overall recommendation
        if analysis.cache_hit_rate > 0.2:
            recommendations.append({
                'type': 'enable_aggressive_caching',
                'priority': 'high',
                'message': f'High cache hit rate ({analysis.cache_hit_rate:.0%}) - enable aggressive caching',
                'estimated_savings': analysis.potential_savings
            })
        
        return recommendations
    
    def clear_cache(self):
        """Clear cache registry"""
        self.cache_registry.clear()


# Global cache awareness instance
_cache_awareness: Optional[CacheAwareness] = None


def get_cache_awareness(config: dict = None) -> CacheAwareness:
    """Get or create global CacheAwareness instance"""
    global _cache_awareness
    if _cache_awareness is None:
        _cache_awareness = CacheAwareness(config)
    return _cache_awareness


def reset_cache_awareness():
    """Reset global cache awareness (for testing)"""
    global _cache_awareness
    _cache_awareness = None
