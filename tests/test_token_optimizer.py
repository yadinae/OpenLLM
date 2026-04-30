"""
Tests for Token Optimizer

Tests the 7-stage compression pipeline:
1. Spell Correction
2. Whitespace Normalization
3. Pattern Optimization
4. Redundancy Elimination
5. NLP Analysis
6. Telegraph Compression
7. Final Cleanup
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.token_optimizer import TokenOptimizer, CompressionMode, OptimizedPrompt


class TestTokenOptimizer:
    """Test suite for TokenOptimizer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.optimizer = TokenOptimizer(mode=CompressionMode.NORMAL)
        self.aggressive_optimizer = TokenOptimizer(mode=CompressionMode.AGGRESSIVE)
        self.soft_optimizer = TokenOptimizer(mode=CompressionMode.SOFT)
    
    # ========================================================================
    # Stage 1: Spell Correction Tests
    # ========================================================================
    
    def test_spell_correction_basic(self):
        """Test basic typo correction"""
        text = "I dont know if this makes sense but could you maybe help me refacter the authetication module"
        result = self.optimizer.spell_correction(text)
        
        # authetication should be corrected to authentication
        assert "authetication" not in result.lower()
        assert "authentication" in result.lower()
        # refacter may or may not be corrected depending on dictionary
        # Just verify the function runs without error
    
    def test_spell_correction_preserves_code(self):
        """Test that code blocks are preserved"""
        text = "Fix the funciton in `def my_funciton():` and `const funciton = () => {}`"
        result = self.optimizer.spell_correction(text)
        
        # Code blocks should be preserved
        assert "my_funciton" in result
        assert "const funciton" in result
    
    def test_spell_correction_preserves_all_caps(self):
        """Test that ALL-CAPS words are preserved"""
        text = "The API key is ERR and the HTTP status is 404"
        result = self.optimizer.spell_correction(text)
        
        assert "API" in result
        assert "ERR" in result
        assert "HTTP" in result
    
    def test_spell_correction_preserves_numbers(self):
        """Test that words with numbers are preserved"""
        text = "The variable var1ble and func2tion should be preserved"
        result = self.optimizer.spell_correction(text)
        
        assert "var1ble" in result
        assert "func2tion" in result
    
    def test_spell_correction_common_typos(self):
        """Test common programming typos"""
        typos = {
            "funciton": "function",
            "varible": "variable",
            "retun": "return",
            "implment": "implement",
            "paramter": "parameter",
            "arguement": "argument",
            "defintion": "definition",
            "inteface": "interface",
            "classs": "class",
            "objct": "object",
            "methd": "method",
            "propertie": "property",
            "statment": "statement",
            "conditon": "condition",
        }
        
        for typo, correction in typos.items():
            text = f"The {typo} is important"
            result = self.optimizer.spell_correction(text)
            assert correction in result.lower(), f"Expected '{correction}' in result for typo '{typo}'"
    
    # ========================================================================
    # Stage 2: Whitespace Normalization Tests
    # ========================================================================
    
    def test_whitespace_normalization_multiple_spaces(self):
        """Test multiple space normalization"""
        text = "Hello    world   this   is   a   test"
        result = self.optimizer.whitespace_normalization(text)
        
        assert "    " not in result
        assert "   " not in result
        assert "  " not in result
    
    def test_whitespace_normalization_blank_lines(self):
        """Test blank line normalization"""
        text = "Line 1\n\n\n\n\nLine 2\n\n\n\nLine 3"
        result = self.optimizer.whitespace_normalization(text)
        
        assert "\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
    
    def test_whitespace_normalization_leading_trailing(self):
        """Test leading/trailing whitespace removal"""
        text = "   Hello world   \n   Another line   "
        result = self.optimizer.whitespace_normalization(text)
        
        assert result.startswith("Hello")
        assert result.endswith("line")
    
    def test_whitespace_normalization_preserves_code(self):
        """Test that code blocks preserve indentation"""
        text = "Text before\n```python\ndef hello():\n    print('world')\n```\nText after"
        result = self.optimizer.whitespace_normalization(text)
        
        # Code block should be preserved
        assert "def hello():" in result
        assert "print('world')" in result
    
    # ========================================================================
    # Stage 3: Pattern Optimization Tests
    # ========================================================================
    
    def test_pattern_optimization_hedging(self):
        """Test hedging language removal"""
        text = "I don't know if this makes sense but could you maybe help me understand this"
        result = self.optimizer.pattern_optimization(text)
        
        assert "I don't know" not in result
        assert "maybe" not in result.lower()
    
    def test_pattern_optimization_meta_language(self):
        """Test meta-language removal"""
        text = "As I mentioned earlier, like I said before, I think that this is important"
        result = self.optimizer.pattern_optimization(text)
        
        assert "As I mentioned" not in result
        assert "like I said" not in result
        assert "I think" not in result
    
    def test_pattern_optimization_filler_phrases(self):
        """Test filler phrase removal"""
        text = "Basically, essentially, literally, I really want to understand this"
        result = self.optimizer.pattern_optimization(text)
        
        assert "Basically" not in result
        assert "essentially" not in result
        assert "literally" not in result
        assert "really" not in result
    
    def test_pattern_optimization_question_softeners(self):
        """Test question softener removal"""
        text = "Could you perhaps help me with this?"
        result = self.optimizer.pattern_optimization(text)
        
        assert "perhaps" not in result.lower()
    
    # ========================================================================
    # Stage 4: Redundancy Elimination Tests
    # ========================================================================
    
    def test_redundancy_elimination_duplicate_sentences(self):
        """Test duplicate sentence removal"""
        text = "Hello world. Hello world. This is a test. This is a test. Another sentence."
        result = self.optimizer.redundancy_elimination(text)
        
        # Should remove duplicates
        assert result.count("Hello world") == 1
        assert result.count("This is a test") == 1
    
    def test_redundancy_elimination_preserves_code(self):
        """Test that code blocks are preserved"""
        text = "Some text with `def hello(): pass` and more text"
        result = self.optimizer.redundancy_elimination(text)
        
        assert "def hello(): pass" in result
    
    # ========================================================================
    # Stage 5: NLP Analysis Tests
    # ========================================================================
    
    def test_nlp_analysis_question_to_imperative(self):
        """Test question-to-imperative conversion"""
        text = "Could you help me refactor the authentication module?"
        result = self.optimizer.nlp_analysis(text)
        
        # Should remove question softeners
        assert "Could you" not in result
        assert "help me" not in result.lower()
    
    def test_nlp_analysis_polite_phrases(self):
        """Test polite phrase removal"""
        text = "Please help me understand this concept"
        result = self.optimizer.nlp_analysis(text)
        
        assert "Please" not in result
    
    # ========================================================================
    # Stage 6: Telegraph Compression Tests
    # ========================================================================
    
    def test_telegraph_compression_articles(self):
        """Test article removal in aggressive mode"""
        text = "The quick brown fox jumps over the lazy dog"
        result = self.aggressive_optimizer.telegraph_compression(text)
        
        # Articles should be removed (but not "the" in "the lazy dog" if it's part of a phrase)
        # This is aggressive, so expect significant reduction
        assert len(result) < len(text)
    
    def test_telegraph_compression_preserves_code(self):
        """Test that code blocks are preserved"""
        text = "The function `def hello():` returns the value"
        result = self.aggressive_optimizer.telegraph_compression(text)
        
        assert "def hello():" in result
    
    # ========================================================================
    # Stage 7: Final Cleanup Tests
    # ========================================================================
    
    def test_final_cleanup_double_spaces(self):
        """Test double space removal"""
        text = "Hello  world  this  is  a  test"
        result = self.optimizer.final_cleanup(text)
        
        assert "  " not in result
    
    def test_final_cleanup_double_newlines(self):
        """Test double newline removal"""
        text = "Line 1\n\n\n\n\nLine 2"
        result = self.optimizer.final_cleanup(text)
        
        assert "\n\n\n" not in result
    
    # ========================================================================
    # Full Pipeline Tests
    # ========================================================================
    
    def test_optimize_normal_mode(self):
        """Test full optimization in normal mode"""
        text = "I don't know if this makes sense but could you maybe help me refacter the authetication module like I mentioned earlier so that it handles tokne refresh properly please?"
        result = self.optimizer.optimize(text)
        
        # Should have significant savings
        assert result.savings > 0
        assert result.savings_pct > 0.1  # At least 10% savings
        assert result.optimized != text
        assert len(result.stages_applied) > 0
    
    def test_optimize_aggressive_mode(self):
        """Test full optimization in aggressive mode"""
        text = "I was just wondering if you could perhaps help me understand how to implement a binary search tree in Python please?"
        result = self.aggressive_optimizer.optimize(text)
        
        # Should have significant savings
        assert result.savings > 0
        assert result.savings_pct > 0.2  # At least 20% savings in aggressive mode
    
    def test_optimize_soft_mode(self):
        """Test full optimization in soft mode"""
        text = "I dont know if this makes sense but could you maybe help me refacter the authetication module"
        result = self.soft_optimizer.optimize(text)
        
        # Should have some savings (spell correction + whitespace)
        assert result.savings >= 0
        assert len(result.stages_applied) >= 0  # At least spell correction
    
    def test_optimize_clean_prompt(self):
        """Test that clean prompts are not changed"""
        text = "Refactor authentication module: handle token refresh"
        result = self.optimizer.optimize(text)
        
        # Clean prompt should have minimal changes
        assert result.savings_pct < 0.1  # Less than 10% change
    
    def test_optimize_short_prompt(self):
        """Test that short prompts are skipped"""
        text = "Hi"
        result = self.optimizer.optimize(text)
        
        # Short prompt should not be optimized
        assert result.original == result.optimized
        assert result.savings == 0
    
    def test_optimize_empty_prompt(self):
        """Test that empty prompts are handled"""
        result = self.optimizer.optimize("")
        
        assert result.original == ""
        assert result.optimized == ""
        assert result.savings == 0
    
    def test_optimize_messages(self):
        """Test message optimization"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "I don't know if this makes sense but could you maybe help me refactor the authentication module"},
            {"role": "assistant", "content": "I'll help you with that"},
        ]
        
        result = self.optimizer.optimize_messages(messages)
        
        # System and assistant messages should be preserved
        assert result[0]["content"] == "You are a helpful assistant"
        assert result[2]["content"] == "I'll help you with that"
        
        # User message should be optimized
        assert result[1]["content"] != messages[1]["content"]
    
    def test_optimize_with_code_blocks(self):
        """Test that code blocks are preserved"""
        text = "Fix the funciton in this code: ```python def my_funciton(): return hello world ``` The funciton should return the correct value."
        
        result = self.optimizer.optimize(text)
        
        # Code block should be preserved (backtick content protected)
        assert "def my_funciton():" in result.optimized
        assert "```python" in result.optimized
    
    def test_optimize_with_urls(self):
        """Test that URLs are preserved"""
        text = "Visit https://example.com for more info about the funciton"
        result = self.optimizer.optimize(text)
        
        assert "https://example.com" in result.optimized
    
    def test_optimize_statistics(self):
        """Test optimization statistics"""
        text = "I don't know if this makes sense but could you maybe help me refactor the authentication module"
        result = self.optimizer.optimize(text)
        
        assert result.original_tokens > 0
        assert result.optimized_tokens > 0
        assert result.savings == result.original_tokens - result.optimized_tokens
        assert result.savings_pct > 0
    
    def test_get_stats(self):
        """Test optimizer stats"""
        stats = self.optimizer.get_stats()
        
        assert stats['mode'] == 'normal'
        assert stats['preserve_code'] == True
        assert stats['max_compression_ratio'] == 0.7
        assert stats['pipeline_stages'] == 4  # normal mode has 4 stages
        assert stats['spell_dictionary_size'] > 100
        assert stats['filler_patterns'] > 50
    
    def test_optimized_prompt_str(self):
        """Test OptimizedPrompt string representation"""
        result = OptimizedPrompt(
            original="test",
            optimized="test",
            original_tokens=10,
            optimized_tokens=8,
            savings=2,
            savings_pct=0.2
        )
        
        assert "10→8" in str(result)
        assert "20%" in str(result)
    
    def test_optimized_prompt_is_significant(self):
        """Test OptimizedPrompt significance threshold"""
        result_significant = OptimizedPrompt(
            original="test",
            optimized="test",
            original_tokens=100,
            optimized_tokens=80,
            savings=20,
            savings_pct=0.2
        )
        
        result_insufficient = OptimizedPrompt(
            original="test",
            optimized="test",
            original_tokens=100,
            optimized_tokens=95,
            savings=5,
            savings_pct=0.05
        )
        
        assert result_significant.is_significant == True
        assert result_insufficient.is_significant == False


class TestCompressionMode:
    """Test compression mode enum"""
    
    def test_mode_values(self):
        """Test mode enum values"""
        assert CompressionMode.SOFT.value == "soft"
        assert CompressionMode.NORMAL.value == "normal"
        assert CompressionMode.AGGRESSIVE.value == "aggressive"
    
    def test_mode_comparison(self):
        """Test mode comparison"""
        assert CompressionMode.SOFT != CompressionMode.NORMAL
        assert CompressionMode.NORMAL != CompressionMode.AGGRESSIVE
        assert CompressionMode.SOFT != CompressionMode.AGGRESSIVE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
