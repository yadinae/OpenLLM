"""HealthScoreTracker 单元测试"""

from __future__ import annotations

import pytest
from openllm.core.health import HealthScoreTracker
from openllm.core.types import ErrorKind


class TestHealthScoreTracker:
    def test_initial_score_is_100(self):
        tracker = HealthScoreTracker()
        assert tracker.get_score("test-provider") == 100.0

    def test_success_keeps_score_high(self):
        tracker = HealthScoreTracker()
        for _ in range(20):
            tracker.record_success("p", 100.0)
        score = tracker.get_score("p")
        assert score > 90

    def test_failures_lower_score(self):
        tracker = HealthScoreTracker()
        for _ in range(10):
            tracker.record_success("p", 100.0)
        for _ in range(5):
            tracker.record_failure("p", ErrorKind.SERVER_ERROR)
        score = tracker.get_score("p")
        assert score < 80

    def test_high_error_rate_drops_score_low(self):
        tracker = HealthScoreTracker()
        for _ in range(10):
            tracker.record_failure("p", ErrorKind.SERVER_ERROR)
        score = tracker.get_score("p")
        assert score < 40

    def test_latency_increase_deducts_points(self):
        tracker = HealthScoreTracker()
        for _ in range(20):
            tracker.record_success("p", 100.0)
        baseline = tracker.get_score("p")
        for _ in range(5):
            tracker.record_success("p", 5000.0)
        after = tracker.get_score("p")
        assert after < baseline

    def test_providers_isolated(self):
        tracker = HealthScoreTracker()
        tracker.record_success("p1", 100.0)
        tracker.record_failure("p2", ErrorKind.TIMEOUT)
        assert tracker.get_score("p1") > tracker.get_score("p2")

    def test_get_latency_p50_empty(self):
        tracker = HealthScoreTracker()
        assert tracker.get_latency_p50("nonexistent") == 0.0

    def test_get_latency_p95_with_data(self):
        tracker = HealthScoreTracker()
        for i in range(10):
            tracker.record_success("p", float(i * 10))
        assert tracker.get_latency_p95("p") > 0
