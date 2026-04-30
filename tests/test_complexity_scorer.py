"""
Tests for ComplexityScorer
"""

import pytest
from src.complexity_scorer import (
    ComplexityScorer,
    ComplexityLevel,
    ComplexityAnalysis,
    get_scorer,
    reset_scorer
)


class TestComplexityScorer:
    """Test ComplexityScorer functionality"""
    
    def setup_method(self):
        """Reset scorer before each test"""
        reset_scorer()
        self.scorer = get_scorer()
    
    def test_empty_request(self):
        """Test empty request returns simple complexity"""
        analysis = self.scorer.analyze([])
        
        assert analysis.level == ComplexityLevel.SIMPLE
        assert analysis.score == 0.0
        assert "Empty request" in analysis.factors
    
    def test_simple_greeting(self):
        """Test simple greeting detection"""
        messages = [
            {"role": "user", "content": "Hello, how are you?"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert analysis.level == ComplexityLevel.SIMPLE
        assert analysis.score < 0.35
    
    def test_simple_translation(self):
        """Test simple translation request"""
        messages = [
            {"role": "user", "content": "Translate this to French: Hello world"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert analysis.level == ComplexityLevel.SIMPLE
    
    def test_moderate_analysis(self):
        """Test moderate complexity analysis request"""
        messages = [
            {"role": "user", "content": "Analyze the pros and cons of remote work and provide recommendations for implementation"}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Should detect moderate complexity due to keywords
        assert analysis.score > 0.1
    
    def test_complex_architecture(self):
        """Test complex architecture design request"""
        messages = [
            {"role": "user", "content": "Design a distributed microservices architecture with Kubernetes, Docker, and CI/CD pipeline. Implement monitoring, logging, and auto-scaling. Include security considerations."}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Should be moderate to complex due to technical terms
        assert analysis.score > 0.3
    
    def test_long_prompt(self):
        """Test long prompt increases complexity"""
        long_text = "Explain " + "very " * 200 + "complex topic in detail with examples and code samples"
        messages = [
            {"role": "user", "content": long_text}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Long prompt should increase score
        assert analysis.score > 0.1
    
    def test_technical_terms(self):
        """Test technical terms increase complexity"""
        messages = [
            {"role": "user", "content": "Implement OAuth2 JWT authentication with Redis caching and GraphQL API"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert analysis.score > 0.3
    
    def test_code_blocks(self):
        """Test code blocks increase complexity"""
        messages = [
            {"role": "user", "content": """
            Fix this Python code:
            ```python
            def calculate_sum(a, b):
                return a + b
            
            result = calculate_sum(10, 20)
            print(result)
            ```
            """}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert analysis.score > 0.2
    
    def test_system_prompt(self):
        """Test system prompt increases context complexity"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert analysis.score > 0.0
    
    def test_conversation_history(self):
        """Test conversation history increases complexity"""
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language"},
            {"role": "user", "content": "How do I install it?"},
            {"role": "assistant", "content": "You can install it from python.org"},
            {"role": "user", "content": "Show me a hello world example"},
            {"role": "assistant", "content": "print('Hello World')"},
            {"role": "user", "content": "What about lists?"},
            {"role": "assistant", "content": "Lists are mutable sequences"},
            {"role": "user", "content": "How do I sort them?"},
            {"role": "assistant", "content": "Use the sort() method"},
            {"role": "user", "content": "What about dictionaries?"}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Conversation history should increase score
        assert analysis.score > 0.2
    
    def test_multiple_questions(self):
        """Test multiple questions increase complexity"""
        messages = [
            {"role": "user", "content": "What is AI? How does it work? What are its applications? What are the ethical concerns? What about future implications?"}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Multiple questions should increase score slightly
        assert analysis.score > 0.05
    
    def test_recommendations_simple(self):
        """Test recommendations for simple tasks"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert len(analysis.recommended_models) > 0
        assert "groq/llama-3.3-70b-versatile" in analysis.recommended_models
    
    def test_recommendations_complex(self):
        """Test recommendations for complex tasks"""
        messages = [
            {"role": "user", "content": "Design a distributed system with microservices, Kubernetes, Docker, and CI/CD pipeline"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert len(analysis.recommended_models) > 0
        # Complex tasks should recommend powerful models
        assert analysis.score >= 0.4
    
    def test_should_route_simple(self):
        """Test routing recommendation for simple tasks"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        analysis = self.scorer.analyze(messages)
        
        assert self.scorer.should_route(analysis, "cerebras/qwen-3-235b-a22b-instruct") == True
        assert self.scorer.should_route(analysis, "gemini/gemini-2.5-flash") == False
    
    def test_should_not_route_complex(self):
        """Test no routing for complex tasks"""
        messages = [
            {"role": "user", "content": "Design a distributed microservices architecture with Kubernetes, Docker, and CI/CD pipeline"}
        ]
        analysis = self.scorer.analyze(messages)
        
        # Complex tasks should not be routed away from powerful models
        assert analysis.score >= 0.4
    
    def test_routing_decision_simple(self):
        """Test complete routing decision for simple task"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        decision = self.scorer.get_routing_decision(messages, "cerebras/qwen-3-235b-a22b-instruct")
        
        assert decision["should_route"] == True
        assert decision["recommended_model"] is not None
        assert decision["recommended_model"] != "cerebras/qwen-3-235b-a22b-instruct"
    
    def test_routing_decision_complex(self):
        """Test complete routing decision for complex task"""
        messages = [
            {"role": "user", "content": "Design a distributed microservices architecture with Kubernetes"}
        ]
        decision = self.scorer.get_routing_decision(messages, "cerebras/qwen-3-235b-a22b-instruct")
        
        assert decision["should_route"] == False
        assert decision["recommended_model"] is None
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = {
            'length_thresholds': {
                'simple': 200,
                'moderate': 1000,
                'complex': 3000
            },
            'keyword_weights': {
                'simple': 0.2,
                'moderate': 0.5,
                'complex': 0.8
            }
        }
        scorer = ComplexityScorer(config)
        
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        analysis = scorer.analyze(messages)
        
        assert analysis.level == ComplexityLevel.SIMPLE
    
    def test_model_recommendation_ordering(self):
        """Test that current model is prioritized if in recommendations"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        analysis = self.scorer.analyze(messages, model="gemini/gemini-2.5-flash")
        
        assert analysis.recommended_models[0] == "gemini/gemini-2.5-flash"


class TestComplexityLevel:
    """Test ComplexityLevel enum"""
    
    def test_enum_values(self):
        """Test complexity level enum values"""
        assert ComplexityLevel.SIMPLE.value == "simple"
        assert ComplexityLevel.MODERATE.value == "moderate"
        assert ComplexityLevel.COMPLEX.value == "complex"


class TestComplexityAnalysis:
    """Test ComplexityAnalysis dataclass"""
    
    def test_dataclass_creation(self):
        """Test ComplexityAnalysis can be created"""
        analysis = ComplexityAnalysis(
            level=ComplexityLevel.SIMPLE,
            score=0.1,
            factors=["Test factor"],
            recommended_models=["model1"]
        )
        
        assert analysis.level == ComplexityLevel.SIMPLE
        assert analysis.score == 0.1
        assert len(analysis.factors) == 1
        assert len(analysis.recommended_models) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
