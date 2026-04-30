"""
Compression Strategy Selector for OpenLLM

Selects optimal compression strategy based on model characteristics.
Different models handle compression differently:
- Claude: Handles implicit reasoning well → aggressive compression
- GPT: Needs explicit instructions → moderate compression
- Open source: Conservative → soft compression
"""

import re
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from src.token_optimizer import CompressionMode

logger = logging.getLogger(__name__)


class CompressionStrategy(str, Enum):
    """Compression strategy types"""
    AGGRESSIVE = "aggressive"  # Claude models
    NORMAL = "normal"          # GPT, Gemini models
    SOFT = "soft"              # Open source models (Llama, Mistral)


@dataclass
class CompressionConfig:
    """Compression configuration for a specific model"""
    mode: CompressionMode = CompressionMode.NORMAL
    preserve_structure: bool = True
    max_compression_ratio: float = 0.5
    min_tokens_to_optimize: int = 10
    preserve_code: bool = True
    
    # Model-specific hints
    hints: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def strategy(self) -> CompressionStrategy:
        """Determine strategy from mode"""
        if self.mode == CompressionMode.AGGRESSIVE:
            return CompressionStrategy.AGGRESSIVE
        elif self.mode == CompressionMode.SOFT:
            return CompressionStrategy.SOFT
        else:
            return CompressionStrategy.NORMAL


# Model family detection patterns
MODEL_FAMILIES = {
    # Claude family - handles implicit reasoning well
    "claude": {
        "patterns": [r'claude', r'anthropic'],
        "strategy": CompressionStrategy.AGGRESSIVE,
        "mode": CompressionMode.AGGRESSIVE,
        "preserve_structure": False,
        "max_compression_ratio": 0.7,
        "description": "Claude handles implicit reasoning - aggressive compression safe"
    },
    # GPT family - needs explicit instructions
    "gpt": {
        "patterns": [r'gpt', r'openai', r'davinci', r'curie', r'babbage', r'ada'],
        "strategy": CompressionStrategy.NORMAL,
        "mode": CompressionMode.NORMAL,
        "preserve_structure": True,
        "max_compression_ratio": 0.5,
        "description": "GPT needs explicit instructions - moderate compression"
    },
    # Gemini family
    "gemini": {
        "patterns": [r'gemini', r'google'],
        "strategy": CompressionStrategy.NORMAL,
        "mode": CompressionMode.NORMAL,
        "preserve_structure": True,
        "max_compression_ratio": 0.5,
        "description": "Gemini handles moderate compression well"
    },
    # Llama family - open source, conservative
    "llama": {
        "patterns": [r'llama', r'codellama'],
        "strategy": CompressionStrategy.SOFT,
        "mode": CompressionMode.SOFT,
        "preserve_structure": True,
        "max_compression_ratio": 0.3,
        "description": "Llama - conservative compression for open source"
    },
    # Mistral family - open source, conservative
    "mistral": {
        "patterns": [r'mistral', r'mixtral'],
        "strategy": CompressionStrategy.SOFT,
        "mode": CompressionMode.SOFT,
        "preserve_structure": True,
        "max_compression_ratio": 0.3,
        "description": "Mistral - conservative compression for open source"
    },
    # Qwen family - open source, moderate
    "qwen": {
        "patterns": [r'qwen', r'alibaba'],
        "strategy": CompressionStrategy.NORMAL,
        "mode": CompressionMode.NORMAL,
        "preserve_structure": True,
        "max_compression_ratio": 0.4,
        "description": "Qwen - moderate compression"
    },
    # Default fallback
    "default": {
        "patterns": [],
        "strategy": CompressionStrategy.SOFT,
        "mode": CompressionMode.SOFT,
        "preserve_structure": True,
        "max_compression_ratio": 0.3,
        "description": "Unknown model - conservative default"
    }
}


class CompressionStrategySelector:
    """
    Selects optimal compression strategy based on model name.
    
    Usage:
        selector = CompressionStrategySelector()
        config = selector.get_strategy("claude-opus-4-6")
        # Returns: CompressionConfig(mode=AGGRESSIVE, max_compression_ratio=0.7, ...)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: Optional custom configuration dict from compression.yaml
        """
        self.config = config or {}
        self._custom_strategies = self.config.get("model_compression", {})
    
    def get_strategy(self, model_name: str) -> CompressionConfig:
        """
        Get compression strategy for a model.
        
        Priority:
        1. Custom config from compression.yaml
        2. Model family detection
        3. Default fallback
        
        Args:
            model_name: Model identifier (e.g., "claude-opus-4-6", "gpt-4o")
        
        Returns:
            CompressionConfig with optimal settings
        """
        if not model_name:
            return self._get_default_config()
        
        model_lower = model_name.lower()
        
        # 1. Check custom config first
        custom_config = self._get_custom_config(model_lower)
        if custom_config:
            return custom_config
        
        # 2. Detect model family
        family_config = self._detect_family_config(model_lower)
        if family_config:
            return family_config
        
        # 3. Default fallback
        return self._get_default_config()
    
    def _get_custom_config(self, model_lower: str) -> Optional[CompressionConfig]:
        """Get custom configuration from compression.yaml"""
        # Check for exact match
        if model_lower in self._custom_strategies:
            custom = self._custom_strategies[model_lower]
            return CompressionConfig(
                mode=CompressionMode(custom.get("mode", "normal")),
                preserve_structure=custom.get("preserve_structure", True),
                max_compression_ratio=custom.get("max_compression_ratio", 0.5),
            )
        
        # Check for partial match (e.g., "claude" matches "claude-opus-4-6")
        for pattern, custom in self._custom_strategies.items():
            if pattern in model_lower:
                return CompressionConfig(
                    mode=CompressionMode(custom.get("mode", "normal")),
                    preserve_structure=custom.get("preserve_structure", True),
                    max_compression_ratio=custom.get("max_compression_ratio", 0.5),
                )
        
        return None
    
    def _detect_family_config(self, model_lower: str) -> Optional[CompressionConfig]:
        """Detect model family and return appropriate config"""
        for family_name, family_info in MODEL_FAMILIES.items():
            if family_name == "default":
                continue
            
            for pattern in family_info["patterns"]:
                if re.search(pattern, model_lower):
                    return CompressionConfig(
                        mode=family_info["mode"],
                        preserve_structure=family_info["preserve_structure"],
                        max_compression_ratio=family_info["max_compression_ratio"],
                        hints={
                            "family": family_name,
                            "strategy": family_info["strategy"].value,
                            "description": family_info["description"],
                        }
                    )
        
        return None
    
    def _get_default_config(self) -> CompressionConfig:
        """Get default compression config"""
        default_info = MODEL_FAMILIES["default"]
        return CompressionConfig(
            mode=default_info["mode"],
            preserve_structure=default_info["preserve_structure"],
            max_compression_ratio=default_info["max_compression_ratio"],
            hints={
                "family": "unknown",
                "strategy": default_info["strategy"].value,
                "description": default_info["description"],
            }
        )
    
    def get_family_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get detailed family information for a model.
        
        Returns:
            Dict with family name, strategy, mode, and description
        """
        config = self.get_strategy(model_name)
        return {
            "model": model_name,
            "family": config.hints.get("family", "unknown"),
            "strategy": config.strategy.value,
            "mode": config.mode.value,
            "preserve_structure": config.preserve_structure,
            "max_compression_ratio": config.max_compression_ratio,
            "description": config.hints.get("description", "Unknown model"),
        }
    
    def list_supported_families(self) -> Dict[str, Dict[str, Any]]:
        """List all supported model families and their strategies"""
        result = {}
        for family_name, family_info in MODEL_FAMILIES.items():
            if family_name == "default":
                continue
            result[family_name] = {
                "patterns": family_info["patterns"],
                "strategy": family_info["strategy"].value,
                "mode": family_info["mode"].value,
                "max_compression_ratio": family_info["max_compression_ratio"],
                "description": family_info["description"],
            }
        return result


# Global selector instance
_selector_instance: Optional[CompressionStrategySelector] = None


def get_compression_selector(config: Optional[Dict] = None) -> CompressionStrategySelector:
    """Get or create the global compression strategy selector"""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = CompressionStrategySelector(config)
    return _selector_instance
