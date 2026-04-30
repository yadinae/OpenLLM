"""
Tests for Compression Strategy Selector

Tests model-specific compression strategy selection:
- Claude: Aggressive compression (70%)
- GPT: Normal compression (50%)
- Llama/Mistral: Soft compression (30%)
- Qwen: Normal compression (40%)
- Gemini: Normal compression (50%)
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compression_strategy import (
    CompressionStrategySelector,
    CompressionConfig,
    CompressionStrategy,
    get_compression_selector,
)
from src.token_optimizer import CompressionMode


class TestCompressionStrategySelector:
    """Test suite for CompressionStrategySelector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.selector = CompressionStrategySelector()
    
    # ========================================================================
    # Claude Family Tests
    # ========================================================================
    
    def test_claude_opus_strategy(self):
        """Test Claude Opus gets aggressive compression"""
        config = self.selector.get_strategy("claude-opus-4-6")
        
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.7
        assert config.preserve_structure == False
        assert config.strategy == CompressionStrategy.AGGRESSIVE
    
    def test_claude_sonnet_strategy(self):
        """Test Claude Sonnet gets aggressive compression"""
        config = self.selector.get_strategy("claude-sonnet-4-6")
        
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.7
    
    def test_claude_haiku_strategy(self):
        """Test Claude Haiku gets aggressive compression"""
        config = self.selector.get_strategy("claude-haiku-3.5")
        
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.7
    
    def test_anthropic_strategy(self):
        """Test Anthropic models get aggressive compression"""
        config = self.selector.get_strategy("anthropic/claude-3-opus")
        
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.7
    
    # ========================================================================
    # GPT Family Tests
    # ========================================================================
    
    def test_gpt4o_strategy(self):
        """Test GPT-4o gets normal compression"""
        config = self.selector.get_strategy("gpt-4o")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
        assert config.preserve_structure == True
        assert config.strategy == CompressionStrategy.NORMAL
    
    def test_gpt4_strategy(self):
        """Test GPT-4 gets normal compression"""
        config = self.selector.get_strategy("gpt-4")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    def test_gpt35_strategy(self):
        """Test GPT-3.5 gets normal compression"""
        config = self.selector.get_strategy("gpt-3.5-turbo")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    def test_openai_strategy(self):
        """Test OpenAI models get normal compression"""
        config = self.selector.get_strategy("openai/gpt-4o-mini")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    def test_davinci_strategy(self):
        """Test Davinci models get normal compression"""
        config = self.selector.get_strategy("davinci-003")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    # ========================================================================
    # Gemini Family Tests
    # ========================================================================
    
    def test_gemini_flash_strategy(self):
        """Test Gemini Flash gets normal compression"""
        config = self.selector.get_strategy("gemini-2.5-flash")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    def test_gemini_pro_strategy(self):
        """Test Gemini Pro gets normal compression"""
        config = self.selector.get_strategy("gemini-pro-1.5")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    def test_google_model_strategy(self):
        """Test Google models get normal compression"""
        config = self.selector.get_strategy("google/gemini-2.5-pro")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    # ========================================================================
    # Llama Family Tests
    # ========================================================================
    
    def test_llama3_strategy(self):
        """Test Llama 3 gets soft compression"""
        config = self.selector.get_strategy("llama-3.3-70b")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
        assert config.preserve_structure == True
        assert config.strategy == CompressionStrategy.SOFT
    
    def test_llama2_strategy(self):
        """Test Llama 2 gets soft compression"""
        config = self.selector.get_strategy("llama-2-70b")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_codellama_strategy(self):
        """Test Code Llama gets soft compression"""
        config = self.selector.get_strategy("codellama-34b")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_groq_llama_strategy(self):
        """Test Groq Llama gets soft compression"""
        config = self.selector.get_strategy("groq/llama-3.3-70b-versatile")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    # ========================================================================
    # Mistral Family Tests
    # ========================================================================
    
    def test_mistral_large_strategy(self):
        """Test Mistral Large gets soft compression"""
        config = self.selector.get_strategy("mistral-large-latest")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_mistral_medium_strategy(self):
        """Test Mistral Medium gets soft compression"""
        config = self.selector.get_strategy("mistral-medium-latest")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_mixtral_strategy(self):
        """Test Mixtral gets soft compression"""
        config = self.selector.get_strategy("mixtral-8x7b")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_groq_mistral_strategy(self):
        """Test Groq Mistral gets soft compression"""
        config = self.selector.get_strategy("groq/mistral-8x7b-32a")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    # ========================================================================
    # Qwen Family Tests
    # ========================================================================
    
    def test_qwen_strategy(self):
        """Test Qwen gets normal compression"""
        config = self.selector.get_strategy("qwen-3-32b")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.4
    
    def test_qwen_large_strategy(self):
        """Test Qwen Large gets normal compression"""
        config = self.selector.get_strategy("qwen-3-235b")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.4
    
    def test_alibaba_model_strategy(self):
        """Test Alibaba models get normal compression"""
        config = self.selector.get_strategy("alibaba/qwen-2.5-72b")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.4
    
    def test_cerebras_qwen_strategy(self):
        """Test Cerebras Qwen gets normal compression"""
        config = self.selector.get_strategy("cerebras/qwen-3-235b-a22b-instruct")
        
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.4
    
    # ========================================================================
    # Unknown Model Tests
    # ========================================================================
    
    def test_unknown_model_strategy(self):
        """Test unknown model gets soft compression (default)"""
        config = self.selector.get_strategy("unknown-model-v1")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
        assert config.strategy == CompressionStrategy.SOFT
    
    def test_empty_model_strategy(self):
        """Test empty model name gets default config"""
        config = self.selector.get_strategy("")
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    def test_none_model_strategy(self):
        """Test None model name gets default config"""
        config = self.selector.get_strategy(None)
        
        assert config.mode == CompressionMode.SOFT
        assert config.max_compression_ratio == 0.3
    
    # ========================================================================
    # Custom Config Tests
    # ========================================================================
    
    def test_custom_config_override(self):
        """Test custom config overrides default"""
        custom_config = {
            "model_compression": {
                "llama": {
                    "mode": "aggressive",
                    "preserve_structure": False,
                    "max_compression_ratio": 0.6,
                }
            }
        }
        
        selector = CompressionStrategySelector(custom_config)
        config = selector.get_strategy("llama-3.3-70b")
        
        # Custom config should override default
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.6
        assert config.preserve_structure == False
    
    def test_custom_config_partial_match(self):
        """Test custom config with partial model name match"""
        custom_config = {
            "model_compression": {
                "claude": {
                    "mode": "normal",
                    "preserve_structure": True,
                    "max_compression_ratio": 0.5,
                }
            }
        }
        
        selector = CompressionStrategySelector(custom_config)
        config = selector.get_strategy("claude-opus-4-6")
        
        # Custom config should override default
        assert config.mode == CompressionMode.NORMAL
        assert config.max_compression_ratio == 0.5
    
    # ========================================================================
    # Family Info Tests
    # ========================================================================
    
    def test_get_family_info_claude(self):
        """Test family info for Claude model"""
        info = self.selector.get_family_info("claude-opus-4-6")
        
        assert info["family"] == "claude"
        assert info["strategy"] == "aggressive"
        assert info["mode"] == "aggressive"
        assert info["max_compression_ratio"] == 0.7
    
    def test_get_family_info_gpt(self):
        """Test family info for GPT model"""
        info = self.selector.get_family_info("gpt-4o")
        
        assert info["family"] == "gpt"
        assert info["strategy"] == "normal"
        assert info["mode"] == "normal"
        assert info["max_compression_ratio"] == 0.5
    
    def test_get_family_info_llama(self):
        """Test family info for Llama model"""
        info = self.selector.get_family_info("llama-3.3-70b")
        
        assert info["family"] == "llama"
        assert info["strategy"] == "soft"
        assert info["mode"] == "soft"
        assert info["max_compression_ratio"] == 0.3
    
    def test_get_family_info_unknown(self):
        """Test family info for unknown model"""
        info = self.selector.get_family_info("unknown-model")
        
        assert info["family"] == "unknown"
        assert info["strategy"] == "soft"
        assert info["mode"] == "soft"
    
    def test_list_supported_families(self):
        """Test listing supported families"""
        families = self.selector.list_supported_families()
        
        assert "claude" in families
        assert "gpt" in families
        assert "llama" in families
        assert "mistral" in families
        assert "qwen" in families
        assert "gemini" in families
        
        # Verify strategies
        assert families["claude"]["strategy"] == "aggressive"
        assert families["gpt"]["strategy"] == "normal"
        assert families["llama"]["strategy"] == "soft"
        assert families["mistral"]["strategy"] == "soft"
        assert families["qwen"]["strategy"] == "normal"
        assert families["gemini"]["strategy"] == "normal"
    
    # ========================================================================
    # Global Selector Tests
    # ========================================================================
    
    def test_get_compression_selector(self):
        """Test global selector singleton"""
        selector1 = get_compression_selector()
        selector2 = get_compression_selector()
        
        assert selector1 is selector2
    
    def test_get_compression_selector_with_config(self):
        """Test global selector with custom config"""
        custom_config = {
            "model_compression": {
                "test": {
                    "mode": "aggressive",
                    "preserve_structure": False,
                    "max_compression_ratio": 0.8,
                }
            }
        }
        
        # Reset global selector
        import src.compression_strategy as cs
        cs._selector_instance = None
        
        selector = get_compression_selector(custom_config)
        config = selector.get_strategy("test-model")
        
        assert config.mode == CompressionMode.AGGRESSIVE
        assert config.max_compression_ratio == 0.8
        
        # Reset again
        cs._selector_instance = None


class TestCompressionConfig:
    """Test suite for CompressionConfig"""
    
    def test_default_config(self):
        """Test default config values"""
        config = CompressionConfig()
        
        assert config.mode == CompressionMode.NORMAL
        assert config.preserve_structure == True
        assert config.max_compression_ratio == 0.5
        assert config.min_tokens_to_optimize == 10
        assert config.preserve_code == True
    
    def test_config_strategy_property(self):
        """Test strategy property from mode"""
        aggressive_config = CompressionConfig(mode=CompressionMode.AGGRESSIVE)
        assert aggressive_config.strategy == CompressionStrategy.AGGRESSIVE
        
        normal_config = CompressionConfig(mode=CompressionMode.NORMAL)
        assert normal_config.strategy == CompressionStrategy.NORMAL
        
        soft_config = CompressionConfig(mode=CompressionMode.SOFT)
        assert soft_config.strategy == CompressionStrategy.SOFT
    
    def test_config_hints(self):
        """Test config hints"""
        config = CompressionConfig(
            hints={
                "family": "claude",
                "strategy": "aggressive",
                "description": "Claude handles implicit reasoning"
            }
        )
        
        assert config.hints["family"] == "claude"
        assert config.hints["strategy"] == "aggressive"


class TestCompressionStrategy:
    """Test compression strategy enum"""
    
    def test_strategy_values(self):
        """Test strategy enum values"""
        assert CompressionStrategy.AGGRESSIVE.value == "aggressive"
        assert CompressionStrategy.NORMAL.value == "normal"
        assert CompressionStrategy.SOFT.value == "soft"
    
    def test_strategy_comparison(self):
        """Test strategy comparison"""
        assert CompressionStrategy.AGGRESSIVE != CompressionStrategy.NORMAL
        assert CompressionStrategy.NORMAL != CompressionStrategy.SOFT
        assert CompressionStrategy.AGGRESSIVE != CompressionStrategy.SOFT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
