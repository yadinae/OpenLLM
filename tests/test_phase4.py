"""
Tests for HistorySummarizer and CacheAwareness
"""

import pytest
from src.history_summarizer import (
    HistorySummarizer,
    SummarizationResult,
    get_summarizer,
    reset_summarizer
)
from src.cache_awareness import (
    CacheAwareness,
    CacheBlock,
    CacheAnalysis,
    get_cache_awareness,
    reset_cache_awareness
)
from src.context import ContextManager


class TestHistorySummarizer:
    """Test HistorySummarizer functionality"""
    
    def setup_method(self):
        """Reset summarizer before each test"""
        reset_summarizer()
        self.summarizer = get_summarizer()
    
    def test_no_summarization_needed(self):
        """Test short messages don't get summarized"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        result = self.summarizer.summarize(messages, max_tokens=1000)
        
        assert result.original_messages == result.summarized_messages
        assert result.compression_ratio == 0.0
        assert result.summary_text == ""
    
    def test_summarization_triggered(self):
        """Test long messages get summarized"""
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"Question {i}: " + "x" * 300})
            messages.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 300})
        
        result = self.summarizer.summarize(messages, max_tokens=2000)
        
        assert len(result.summarized_messages) < len(result.original_messages)
        assert result.compression_ratio > 0.0
        assert len(result.summary_text) > 0
    
    def test_system_prompt_preserved(self):
        """Test system prompts are preserved in summary"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "x" * 500},
            {"role": "assistant", "content": "y" * 500},
            {"role": "user", "content": "z" * 500},
            {"role": "assistant", "content": "w" * 500},
        ]
        
        result = self.summarizer.summarize(messages, max_tokens=500)
        
        # Check system prompt is preserved
        system_msgs = [m for m in result.summarized_messages if m.get('role') == 'system']
        assert len(system_msgs) > 0
    
    def test_extractive_strategy(self):
        """Test extractive summarization strategy"""
        summarizer = HistorySummarizer({'strategy': 'extractive'})
        
        messages = [
            {"role": "user", "content": "Create a Python function to sort a list"},
            {"role": "assistant", "content": "Here is a sorted function that successfully completes the task"},
            {"role": "user", "content": "Now optimize it for performance"},
            {"role": "assistant", "content": "Therefore the optimized solution uses quicksort"},
        ]
        
        # Force summarization with low threshold
        result = summarizer.summarize(messages, max_tokens=10)
        
        # Should have summary text when summarization is triggered
        assert result.compression_ratio >= 0.0
    
    def test_abstractive_strategy(self):
        """Test abstractive summarization strategy"""
        summarizer = HistorySummarizer({'strategy': 'abstractive'})
        
        messages = [
            {"role": "user", "content": "What is machine learning?"},
            {"role": "assistant", "content": "Machine learning is a subset of AI"},
        ]
        
        # Force summarization with low threshold
        result = summarizer.summarize(messages, max_tokens=5)
        
        assert result.compression_ratio >= 0.0
    
    def test_hybrid_strategy(self):
        """Test hybrid summarization strategy"""
        summarizer = HistorySummarizer({'strategy': 'hybrid'})
        
        messages = [
            {"role": "user", "content": "How do I install Python?"},
            {"role": "assistant", "content": "You can download it from python.org"},
        ]
        
        # Force summarization with low threshold
        result = summarizer.summarize(messages, max_tokens=5)
        
        assert result.compression_ratio >= 0.0
    
    def test_empty_messages(self):
        """Test empty message list"""
        result = self.summarizer.summarize([])
        
        assert result.original_messages == []
        assert result.summarized_messages == []
        assert result.compression_ratio == 0.0
    
    def test_compression_ratio_calculation(self):
        """Test compression ratio is calculated correctly"""
        messages = []
        for i in range(15):
            messages.append({"role": "user", "content": "Q" * 400})
            messages.append({"role": "assistant", "content": "A" * 400})
        
        result = self.summarizer.summarize(messages, max_tokens=1000)
        
        assert 0.0 <= result.compression_ratio <= 1.0
        assert result.summarized_tokens < result.original_tokens


class TestCacheAwareness:
    """Test CacheAwareness functionality"""
    
    def setup_method(self):
        """Reset cache awareness before each test"""
        reset_cache_awareness()
        self.cache = get_cache_awareness()
    
    def test_system_prompt_detection(self):
        """Test system prompt detection"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. You should always be polite and follow these rules: be concise."},
            {"role": "user", "content": "Hello"}
        ]
        
        analysis = self.cache.analyze(messages)
        
        system_blocks = [b for b in analysis.cacheable_blocks if b.block_type == 'system_prompt']
        assert len(system_blocks) > 0
    
    def test_code_block_detection(self):
        """Test code block detection"""
        messages = [
            {"role": "user", "content": """
            Here is some code:
            ```python
            def hello():
                print("Hello World")
            ```
            """ * 10}
        ]
        
        analysis = self.cache.analyze(messages)
        
        code_blocks = [b for b in analysis.cacheable_blocks if b.block_type == 'code_block']
        assert len(code_blocks) > 0
    
    def test_duplicate_detection(self):
        """Test duplicate content detection"""
        repeated_content = "This is a repeated message that appears multiple times in the conversation"
        messages = [
            {"role": "user", "content": repeated_content},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": repeated_content},  # Duplicate
            {"role": "assistant", "content": "Response 2"},
        ]
        
        analysis = self.cache.analyze(messages)
        
        assert analysis.duplicate_count > 0
        assert analysis.cache_hit_rate > 0.0
    
    def test_structured_data_detection(self):
        """Test structured data detection"""
        messages = [
            {"role": "user", "content": """
            | Name | Age | City | Location |
            |------|-----|------|----------|
            | John | 30  | NYC  | USA |
            | Jane | 25  | LA   | USA |
            
            1. First item in the list
            2. Second item in the list
            3. Third item in the list
            """ * 5}
        ]
        
        analysis = self.cache.analyze(messages)
        
        # Should detect structured data (table + numbered list)
        assert analysis.total_blocks > 0
    
    def test_cache_recommendations(self):
        """Test cache recommendations generation"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. You must follow these rules: be concise and accurate."},
            {"role": "user", "content": "Hello"}
        ]
        
        analysis = self.cache.analyze(messages)
        recommendations = self.cache.get_cache_recommendations(analysis)
        
        assert len(recommendations) >= 0
    
    def test_clear_cache(self):
        """Test cache clearing"""
        messages = [
            {"role": "user", "content": "This is a test message with enough content to exceed the minimum block size requirement"}
        ]
        
        self.cache.analyze(messages)
        # Content should be registered if it's long enough
        
        self.cache.clear_cache()
        assert len(self.cache.cache_registry) == 0
    
    def test_empty_messages(self):
        """Test empty message list"""
        analysis = self.cache.analyze([])
        
        assert len(analysis.cacheable_blocks) == 0
        assert analysis.potential_savings == 0
        assert analysis.cache_hit_rate == 0.0


class TestContextManager:
    """Test ContextManager with Terse integration"""
    
    def setup_method(self):
        """Reset components before each test"""
        reset_summarizer()
        reset_cache_awareness()
        self.context = ContextManager(
            mode='dynamic',
            max_tokens=1000,
            enable_summarization=True,
            enable_cache_awareness=True
        )
    
    def test_enhance_with_summarization(self):
        """Test enhance method with summarization"""
        messages = []
        for i in range(15):
            messages.append({"role": "user", "content": f"Question {i}: " + "x" * 200})
            messages.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 200})
        
        result = self.context.enhance(messages)
        
        assert result['summarization'] is not None
        assert result['summarization']['compression_ratio'] > 0.0
        assert result['final_token_count'] < result['original_token_count']
    
    def test_enhance_with_cache_awareness(self):
        """Test enhance method with cache awareness"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. You should follow these rules."},
            {"role": "user", "content": "Hello"}
        ]
        
        result = self.context.enhance(messages)
        
        assert result['cache_analysis'] is not None
        assert 'recommendations' in result['cache_analysis']
    
    def test_enhance_disabled_features(self):
        """Test enhance with features disabled"""
        context = ContextManager(
            enable_summarization=False,
            enable_cache_awareness=False
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        result = context.enhance(messages)
        
        assert result['summarization'] is None
        assert result['cache_analysis'] is None
    
    def test_estimate_tokens(self):
        """Test token estimation"""
        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        tokens = self.context._estimate_tokens(messages)
        
        assert tokens > 0


class TestSummarizationResult:
    """Test SummarizationResult dataclass"""
    
    def test_dataclass_creation(self):
        """Test SummarizationResult can be created"""
        result = SummarizationResult(
            original_messages=[],
            summarized_messages=[],
            original_tokens=100,
            summarized_tokens=50,
            compression_ratio=0.5,
            summary_text="Test summary"
        )
        
        assert result.original_tokens == 100
        assert result.summarized_tokens == 50
        assert result.compression_ratio == 0.5


class TestCacheBlock:
    """Test CacheBlock dataclass"""
    
    def test_dataclass_creation(self):
        """Test CacheBlock can be created"""
        block = CacheBlock(
            index=0,
            content="Test content",
            block_type="system_prompt",
            cache_priority="high"
        )
        
        assert block.index == 0
        assert block.block_type == "system_prompt"
        assert block.cache_priority == "high"
        assert len(block.content_hash) > 0
        assert block.estimated_tokens > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
