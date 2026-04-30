"""
Request Complexity Scorer for OpenLLM

Analyzes incoming requests to determine their complexity level,
enabling automatic routing to cost-effective models.

Complexity levels:
- simple: Basic questions, translations, formatting
- moderate: Summarization, analysis, simple coding
- complex: Multi-step reasoning, architecture design, debugging
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ComplexityAnalysis:
    """Result of complexity analysis"""
    level: ComplexityLevel
    score: float  # 0.0 - 1.0
    factors: list = field(default_factory=list)
    recommended_models: list = field(default_factory=list)


class ComplexityScorer:
    """
    Analyzes request complexity to enable intelligent model routing.
    
    Scoring factors:
    - Task type (keyword-based)
    - Prompt length (token count)
    - Context complexity (system messages, conversation history)
    - Language complexity (technical terms, code blocks)
    """
    
    # Complexity keywords by category
    SIMPLE_KEYWORDS = [
        "translate", "翻译", "format", "格式化", "convert", "转换",
        "simple", "basic", "简单", "基础", "greet", "问候",
        "hello", "你好", "thanks", "谢谢", "yes", "是",
        "no", "否", "ok", "好的", "list", "列表",
        "summarize", "总结", "brief", "简短", "short", "短"
    ]
    
    MODERATE_KEYWORDS = [
        "analyze", "分析", "explain", "解释", "compare", "比较",
        "review", "审查", "summarize", "摘要", "rewrite", "重写",
        "improve", "改进", "optimize", "优化", "debug", "调试",
        "fix", "修复", "test", "测试", "document", "文档",
        "create", "创建", "generate", "生成", "design", "设计"
    ]
    
    COMPLEX_KEYWORDS = [
        "architect", "架构", "design pattern", "设计模式", "refactor", "重构",
        "system design", "系统设计", "algorithm", "算法", "optimize", "优化",
        "debug", "调试", "security", "安全", "performance", "性能",
        "distributed", "分布式", "concurrent", "并发", "scale", "扩展",
        "implement", "实现", "build", "构建", "deploy", "部署",
        "machine learning", "机器学习", "neural network", "神经网络",
        "multi-step", "多步骤", "reasoning", "推理", "planning", "规划"
    ]
    
    # Technical terms that increase complexity
    TECHNICAL_TERMS = [
        "API", "REST", "GraphQL", "SQL", "NoSQL", "HTTP", "TCP",
        "UDP", "DNS", "CDN", "Load Balancer", "Cache", "Redis",
        "Kubernetes", "Docker", "CI/CD", "DevOps", "Microservices",
        "OAuth", "JWT", "SSL", "TLS", "Encryption", "Hash",
        "Python", "JavaScript", "TypeScript", "Rust", "Go", "Java",
        "React", "Vue", "Angular", "Next.js", "Django", "Flask",
        "TensorFlow", "PyTorch", "Transformer", "Attention", "GPU",
        "CPU", "Memory", "Thread", "Process", "Async", "Sync"
    ]
    
    # Code block patterns
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')
    INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
    
    # Question patterns
    MULTI_QUESTION_PATTERN = re.compile(r'[？?][^。!?]*[？?]')
    
    def __init__(self, config: dict = None):
        """
        Initialize ComplexityScorer
        
        Args:
            config: Optional configuration dict
                - length_thresholds: Dict with 'simple', 'moderate', 'complex' token counts
                - keyword_weights: Dict with weights for keyword categories
                - technical_weight: Weight for technical terms
                - code_weight: Weight for code blocks
        """
        self.config = config or {}
        self.length_thresholds = self.config.get('length_thresholds', {
            'simple': 500,
            'moderate': 2000,
            'complex': 5000
        })
        self.keyword_weights = self.config.get('keyword_weights', {
            'simple': 0.2,
            'moderate': 0.5,
            'complex': 0.9
        })
        self.technical_weight = self.config.get('technical_weight', 0.15)
        self.code_weight = self.config.get('code_weight', 0.25)
    
    def analyze(self, messages: list, model: str = None) -> ComplexityAnalysis:
        """
        Analyze request complexity
        
        Args:
            messages: List of message dicts (role, content)
            model: Target model (for recommendations)
        
        Returns:
            ComplexityAnalysis with level, score, factors, and recommendations
        """
        if not messages:
            return ComplexityAnalysis(
                level=ComplexityLevel.SIMPLE,
                score=0.0,
                factors=["Empty request"],
                recommended_models=[]
            )
        
        # Extract text content
        user_messages = [m for m in messages if m.get('role') == 'user']
        system_messages = [m for m in messages if m.get('role') == 'system']
        
        user_text = ' '.join(m.get('content', '') for m in user_messages)
        system_text = ' '.join(m.get('content', '') for m in system_messages)
        
        # Score components
        length_score = self._score_length(user_text)
        keyword_score = self._score_keywords(user_text)
        technical_score = self._score_technical(user_text)
        code_score = self._score_code(user_text)
        context_score = self._score_context(system_messages, messages)
        
        # Weighted total
        total_score = (
            length_score * 0.20 +
            keyword_score * 0.35 +
            technical_score * 0.20 +
            code_score * 0.10 +
            context_score * 0.15
        )
        
        # Determine level
        if total_score < 0.35:
            level = ComplexityLevel.SIMPLE
        elif total_score < 0.65:
            level = ComplexityLevel.MODERATE
        else:
            level = ComplexityLevel.COMPLEX
        
        # Build factors list
        factors = []
        if length_score > 0.7:
            factors.append(f"Long prompt ({len(user_text)} chars)")
        if keyword_score > 0.7:
            factors.append("Complex task keywords detected")
        if technical_score > 0.5:
            factors.append(f"{technical_score:.0f} technical terms found")
        if code_score > 0.5:
            factors.append(f"Code blocks detected ({code_score:.0f} blocks)")
        if context_score > 0.5:
            factors.append("Complex context (system prompts + history)")
        
        # Generate recommendations
        recommendations = self._get_recommendations(level, model)
        
        return ComplexityAnalysis(
            level=level,
            score=round(total_score, 3),
            factors=factors,
            recommended_models=recommendations
        )
    
    def _score_length(self, text: str) -> float:
        """Score based on text length (proxy for token count)"""
        if not text:
            return 0.0
        
        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(text) / 4
        
        if estimated_tokens <= self.length_thresholds['simple']:
            return 0.1
        elif estimated_tokens <= self.length_thresholds['moderate']:
            return 0.4
        elif estimated_tokens <= self.length_thresholds['complex']:
            return 0.7
        else:
            return 1.0
    
    def _score_keywords(self, text: str) -> float:
        """Score based on task keywords"""
        text_lower = text.lower()
        
        simple_count = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in text_lower)
        moderate_count = sum(1 for kw in self.MODERATE_KEYWORDS if kw in text_lower)
        complex_count = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in text_lower)
        
        # Weighted score - boost moderate and complex keywords
        score = 0.0
        if simple_count > 0 and moderate_count == 0 and complex_count == 0:
            score = simple_count * 0.15
        elif moderate_count > 0:
            score = 0.3 + moderate_count * 0.2
        if complex_count > 0:
            score = max(score, 0.6 + complex_count * 0.15)
        
        return min(score, 1.0)
    
    def _score_technical(self, text: str) -> float:
        """Score based on technical term density"""
        if not text:
            return 0.0
        
        technical_count = sum(1 for term in self.TECHNICAL_TERMS if term in text)
        
        # Boost score for technical terms
        if technical_count == 0:
            return 0.0
        elif technical_count == 1:
            return 0.3
        elif technical_count <= 3:
            return 0.6
        else:
            return 0.9
    
    def _score_code(self, text: str) -> float:
        """Score based on code block presence"""
        code_blocks = self.CODE_BLOCK_PATTERN.findall(text)
        inline_codes = self.INLINE_CODE_PATTERN.findall(text)
        
        code_score = len(code_blocks) * 0.3 + len(inline_codes) * 0.1
        return min(code_score * self.code_weight * 5, 1.0)
    
    def _score_context(self, system_messages: list, all_messages: list) -> float:
        """Score based on context complexity"""
        score = 0.0
        
        # System prompt presence
        if system_messages:
            score += 0.2
        
        # Conversation history length
        history_length = len(all_messages)
        if history_length > 10:
            score += 0.5
        elif history_length > 5:
            score += 0.35
        elif history_length > 2:
            score += 0.15
        
        # Multiple questions
        user_text = ' '.join(m.get('content', '') for m in all_messages if m.get('role') == 'user')
        question_count = user_text.count('?') + user_text.count('？')
        if question_count > 3:
            score += 0.3
        elif question_count > 1:
            score += 0.15
        
        return min(score, 1.0)
    
    def _get_recommendations(self, level: ComplexityLevel, model: str = None) -> list:
        """Get model recommendations based on complexity level"""
        # Default recommendations by complexity
        recommendations = {
            ComplexityLevel.SIMPLE: [
                "groq/llama-3.3-70b-versatile",  # Fast, cheap
                "gemini/gemini-2.5-flash",        # Very fast, large context
                "mistral/mistral-medium-latest"   # Balanced
            ],
            ComplexityLevel.MODERATE: [
                "cerebras/qwen-3-235b-a22b-instruct",  # Powerful
                "groq/qwen-3-32b",                      # Good balance
                "gemini/gemini-2.5-flash"               # Fast fallback
            ],
            ComplexityLevel.COMPLEX: [
                "cerebras/qwen-3-235b-a22b-instruct",  # Most powerful
                "groq/qwen-3-32b",                      # Strong alternative
                "groq/llama-3.3-70b-versatile"          # Fallback
            ]
        }
        
        recs = recommendations.get(level, recommendations[ComplexityLevel.MODERATE])
        
        # If current model is in recommendations, move it to front
        if model and model in recs:
            recs = [model] + [r for r in recs if r != model]
        
        return recs
    
    def should_route(self, analysis: ComplexityAnalysis, current_model: str) -> bool:
        """
        Determine if request should be routed to a different model
        
        Args:
            analysis: Complexity analysis result
            current_model: Currently selected model
        
        Returns:
            True if routing to a cheaper model is recommended
        """
        if analysis.level == ComplexityLevel.COMPLEX:
            return False  # Always use powerful model for complex tasks
        
        # For simple/moderate tasks, recommend routing if current model is expensive
        expensive_models = [
            "cerebras/qwen-3-235b-a22b-instruct",
            "claude-opus-4-6",
            "gpt-4o"
        ]
        
        return current_model in expensive_models
    
    def get_routing_decision(self, messages: list, current_model: str) -> dict:
        """
        Complete routing decision
        
        Args:
            messages: Request messages
            current_model: Currently selected model
        
        Returns:
            Dict with routing decision:
            {
                "should_route": bool,
                "complexity": ComplexityLevel,
                "score": float,
                "recommended_model": str or None,
                "reason": str
            }
        """
        analysis = self.analyze(messages, current_model)
        
        if not self.should_route(analysis, current_model):
            return {
                "should_route": False,
                "complexity": analysis.level.value,
                "score": analysis.score,
                "recommended_model": None,
                "reason": f"Complex task ({analysis.level.value}, score={analysis.score:.2f}) requires powerful model"
            }
        
        # Get best recommendation
        recommended = analysis.recommended_models[0] if analysis.recommended_models else None
        
        if recommended and recommended != current_model:
            return {
                "should_route": True,
                "complexity": analysis.level.value,
                "score": analysis.score,
                "recommended_model": recommended,
                "reason": f"{analysis.level.value.capitalize()} task (score={analysis.score:.2f}) can use cheaper model"
            }
        
        return {
            "should_route": False,
            "complexity": analysis.level.value,
            "score": analysis.score,
            "recommended_model": None,
            "reason": "No better model available for this complexity level"
        }


# Global scorer instance
_scorer: Optional[ComplexityScorer] = None


def get_scorer(config: dict = None) -> ComplexityScorer:
    """Get or create global ComplexityScorer instance"""
    global _scorer
    if _scorer is None:
        _scorer = ComplexityScorer(config)
    return _scorer


def reset_scorer():
    """Reset global scorer (for testing)"""
    global _scorer
    _scorer = None
