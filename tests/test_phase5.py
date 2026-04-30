"""
Tests for TokenMonitor and GitDiffCompressor
"""

import pytest
import time
from src.token_monitor import (
    TokenMonitor,
    SessionStats,
    GlobalStats,
    Anomaly,
    AnomalySeverity,
    get_monitor,
    reset_monitor
)
from src.git_diff_compressor import (
    GitDiffCompressor,
    DiffCompressionResult,
    get_diff_compressor,
    reset_diff_compressor
)


class TestTokenMonitor:
    """Test TokenMonitor functionality"""
    
    def setup_method(self):
        """Reset monitor before each test"""
        reset_monitor()
        self.monitor = get_monitor()
    
    def test_record_request(self):
        """Test recording a request/response pair"""
        request = {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        response = {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cache_tokens": 20}
        }
        
        session = self.monitor.record_request("test-session", request, response)
        
        assert session.session_id == "test-session"
        assert session.turns == 1
        assert session.input_tokens == 100
        assert session.output_tokens == 50
        assert session.cache_tokens == 20
        assert session.cost > 0
    
    def test_multiple_requests(self):
        """Test recording multiple requests"""
        for i in range(5):
            request = {"usage": {"prompt_tokens": 100}}
            response = {"usage": {"completion_tokens": 50}}
            self.monitor.record_request("test-session", request, response)
        
        session = self.monitor.get_session_stats("test-session")
        
        assert session.turns == 5
        assert session.input_tokens == 500
        assert session.output_tokens == 250
    
    def test_compression_tracking(self):
        """Test compression info tracking"""
        request = {"usage": {"prompt_tokens": 1000}}
        response = {"usage": {"completion_tokens": 500}}
        compression = {"tokens_saved": 400}
        
        session = self.monitor.record_request("test-session", request, response, compression)
        
        assert session.compressed_tokens == 400
        assert session.compression_ratio == 0.4
    
    def test_cost_calculation(self):
        """Test cost calculation"""
        request = {"usage": {"prompt_tokens": 10000}}
        response = {"usage": {"completion_tokens": 5000}}
        
        session = self.monitor.record_request("test-session", request, response)
        
        # Expected: (10000/1000 * 0.005) + (5000/1000 * 0.015) = 0.05 + 0.075 = 0.125
        assert abs(session.cost - 0.125) < 0.001
    
    def test_global_stats(self):
        """Test global statistics"""
        # Record some requests
        for i in range(3):
            request = {"usage": {"prompt_tokens": 100}}
            response = {"usage": {"completion_tokens": 50}}
            self.monitor.record_request(f"session-{i}", request, response)
        
        global_stats = self.monitor.get_global_stats()
        
        assert global_stats.total_sessions == 3
        assert global_stats.total_turns == 3
        assert global_stats.total_input_tokens == 300
        assert global_stats.total_output_tokens == 150
        assert global_stats.total_cost > 0
    
    def test_session_list(self):
        """Test session list retrieval"""
        for i in range(5):
            request = {"usage": {"prompt_tokens": 100}}
            response = {"usage": {"completion_tokens": 50}}
            self.monitor.record_request(f"session-{i}", request, response)
        
        sessions = self.monitor.get_session_list(limit=3)
        
        assert len(sessions) == 3
        # Should be sorted by last_activity (most recent first)
        assert sessions[0].session_id == "session-4"
    
    def test_anomaly_detection_duplicate_calls(self):
        """Test duplicate tool call anomaly detection"""
        request = {"usage": {"prompt_tokens": 100}}
        response = {"usage": {"completion_tokens": 50}}
        
        session = self.monitor.record_request("test-session", request, response)
        session.duplicate_tool_calls = 5  # Simulate duplicate calls
        
        anomalies = self.monitor.detect_anomalies("test-session")
        
        duplicate_anomalies = [a for a in anomalies if a.type == 'duplicate_tool_calls']
        assert len(duplicate_anomalies) > 0
        assert duplicate_anomalies[0].severity == AnomalySeverity.WARNING
    
    def test_anomaly_detection_context_overflow(self):
        """Test context overflow anomaly detection"""
        request = {"usage": {"prompt_tokens": 110000}}
        response = {"usage": {"completion_tokens": 50}}
        
        session = self.monitor.record_request("test-session", request, response)
        session.max_context = 128000
        
        anomalies = self.monitor.detect_anomalies("test-session")
        
        overflow_anomalies = [a for a in anomalies if a.type == 'context_overflow']
        assert len(overflow_anomalies) > 0
        assert overflow_anomalies[0].severity == AnomalySeverity.CRITICAL
    
    def test_export_session_report(self):
        """Test session report export"""
        request = {"usage": {"prompt_tokens": 1000}}
        response = {"usage": {"completion_tokens": 500}}
        compression = {"tokens_saved": 400}
        
        self.monitor.record_request("test-session", request, response, compression)
        
        report = self.monitor.export_report("test-session")
        
        assert report['session_id'] == 'test-session'
        assert report['turns'] == 1
        assert report['input_tokens'] == 1000
        assert report['output_tokens'] == 500
        assert report['compressed_tokens'] == 400
        assert report['compression_ratio'] == 0.4
        assert report['cost'] > 0
    
    def test_export_global_report(self):
        """Test global report export"""
        request = {"usage": {"prompt_tokens": 100}}
        response = {"usage": {"completion_tokens": 50}}
        
        self.monitor.record_request("session-1", request, response)
        self.monitor.record_request("session-2", request, response)
        
        report = self.monitor.export_report()
        
        assert report['total_sessions'] == 2
        assert report['total_turns'] == 2
        assert 'recent_anomalies' in report
    
    def test_clear_session(self):
        """Test clearing a session"""
        request = {"usage": {"prompt_tokens": 100}}
        response = {"usage": {"completion_tokens": 50}}
        
        self.monitor.record_request("test-session", request, response)
        assert self.monitor.get_session_stats("test-session") is not None
        
        self.monitor.clear_session("test-session")
        assert self.monitor.get_session_stats("test-session") is None
    
    def test_clear_all(self):
        """Test clearing all data"""
        request = {"usage": {"prompt_tokens": 100}}
        response = {"usage": {"completion_tokens": 50}}
        
        self.monitor.record_request("session-1", request, response)
        self.monitor.record_request("session-2", request, response)
        
        self.monitor.clear_all()
        
        assert len(self.monitor.sessions) == 0
        assert len(self.monitor.anomalies) == 0
    
    def test_session_eviction(self):
        """Test session eviction when max_sessions reached"""
        monitor = TokenMonitor({'max_sessions': 3})
        
        request = {"usage": {"prompt_tokens": 100}}
        response = {"usage": {"completion_tokens": 50}}
        
        for i in range(5):
            monitor.record_request(f"session-{i}", request, response)
        
        # Should have evicted oldest sessions
        assert len(monitor.sessions) == 3
        assert "session-0" not in monitor.sessions
        assert "session-4" in monitor.sessions


class TestGitDiffCompressor:
    """Test GitDiffCompressor functionality"""
    
    def setup_method(self):
        """Reset compressor before each test"""
        reset_diff_compressor()
        self.compressor = get_diff_compressor()
    
    def test_basic_compression(self):
        """Test basic diff compression"""
        diff = """diff --git a/file.py b/file.py
index 1234567..89abcde 100644
--- a/file.py
+++ b/file.py
@@ -1,5 +1,6 @@
 def hello():
+    # Added comment
     print("Hello")
-    print("World")
+    print("Universe")
"""
        result = self.compressor.compress(diff)
        
        assert result.compressed_diff != ""
        assert result.compression_ratio > 0.0
        assert result.files_changed == 1
        assert result.lines_added > 0
        assert result.lines_removed > 0
    
    def test_metadata_removal(self):
        """Test metadata removal"""
        diff = """diff --git a/file.py b/file.py
index 1234567..89abcde 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old line
+new line
"""
        result = self.compressor.compress(diff)
        
        # Should not contain metadata
        assert "index" not in result.compressed_diff
        assert "--- a/" not in result.compressed_diff
        assert "+++ b/" not in result.compressed_diff
    
    def test_context_compression(self):
        """Test context line compression"""
        # Create diff with many context lines
        context_lines = '\n'.join([f' context line {i}' for i in range(20)])
        diff = f"""diff --git a/file.py b/file.py
@@ -1,25 +1,25 @@
{context_lines}
-old line
+new line
"""
        compressor = GitDiffCompressor({'max_context_lines': 2})
        result = compressor.compress(diff)
        
        # Should compress context
        assert "unchanged lines compressed" in result.compressed_diff
    
    def test_multiple_files(self):
        """Test compression of multi-file diff"""
        diff = """diff --git a/file1.py b/file1.py
@@ -1,3 +1,3 @@
-old1
+new1
diff --git a/file2.py b/file2.py
@@ -1,3 +1,3 @@
-old2
+new2
"""
        result = self.compressor.compress(diff)
        
        assert result.files_changed == 2
    
    def test_empty_diff(self):
        """Test empty diff handling"""
        result = self.compressor.compress("")
        
        assert result.original_diff == ""
        assert result.compressed_diff == ""
        assert result.compression_ratio == 0.0
    
    def test_summary_inclusion(self):
        """Test summary statistics inclusion"""
        diff = """diff --git a/file.py b/file.py
@@ -1,3 +1,4 @@
 context
+added line
 context
"""
        result = self.compressor.compress(diff)
        
        assert result.stats_summary != ""
        assert "file" in result.stats_summary.lower() or "changed" in result.stats_summary.lower()
    
    def test_compression_ratio(self):
        """Test compression ratio calculation"""
        # Large diff with lots of context
        context = '\n'.join([f' line {i}' for i in range(100)])
        diff = f"""diff --git a/file.py b/file.py
@@ -1,105 +1,105 @@
{context}
-old line
+new line
"""
        compressor = GitDiffCompressor({'max_context_lines': 2})
        result = compressor.compress(diff)
        
        assert 0.0 <= result.compression_ratio <= 1.0
        assert result.compressed_tokens < result.original_tokens


class TestSessionStats:
    """Test SessionStats dataclass"""
    
    def test_total_tokens(self):
        """Test total_tokens property"""
        stats = SessionStats(
            session_id="test",
            input_tokens=100,
            output_tokens=50
        )
        
        assert stats.total_tokens == 150
    
    def test_fill_rate(self):
        """Test fill_rate property"""
        stats = SessionStats(
            session_id="test",
            input_tokens=100000,
            max_context=128000
        )
        
        assert abs(stats.fill_rate - 0.78125) < 0.001
    
    def test_compression_ratio(self):
        """Test compression_ratio property"""
        stats = SessionStats(
            session_id="test",
            input_tokens=1000,
            compressed_tokens=400
        )
        
        assert stats.compression_ratio == 0.4
    
    def test_zero_division_protection(self):
        """Test protection against division by zero"""
        stats = SessionStats(session_id="test")
        
        assert stats.fill_rate == 0.0
        assert stats.compression_ratio == 0.0


class TestAnomaly:
    """Test Anomaly dataclass"""
    
    def test_anomaly_creation(self):
        """Test anomaly can be created"""
        anomaly = Anomaly(
            type="test",
            severity=AnomalySeverity.WARNING,
            message="Test anomaly",
            session_id="test-session"
        )
        
        assert anomaly.type == "test"
        assert anomaly.severity == AnomalySeverity.WARNING
        assert anomaly.session_id == "test-session"


class TestDiffCompressionResult:
    """Test DiffCompressionResult dataclass"""
    
    def test_result_creation(self):
        """Test result can be created"""
        result = DiffCompressionResult(
            original_diff="test diff",
            compressed_diff="compressed",
            original_tokens=100,
            compressed_tokens=50,
            compression_ratio=0.5,
            files_changed=1,
            lines_added=5,
            lines_removed=3
        )
        
        assert result.files_changed == 1
        assert result.lines_added == 5
        assert result.lines_removed == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
