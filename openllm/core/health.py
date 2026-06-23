"""健康评分追踪器 — 滚动窗口内追踪 provider 健康状态"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from .types import ErrorKind


class HealthScoreTracker:
    """滚动窗口健康评分，0-100"""

    WINDOW_SIZE = 100
    LATENCY_DECAY = 0.9

    def __init__(self) -> None:
        self._successes: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._failures: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )

    def record_success(self, provider: str, latency_ms: float = 0.0) -> None:
        self._successes[provider].append({"time": time.time()})
        if latency_ms > 0:
            self._latencies[provider].append(latency_ms)

    def record_failure(self, provider: str, error_kind: ErrorKind) -> None:
        self._failures[provider].append({
            "time": time.time(),
            "kind": error_kind.value,
        })

    def get_score(self, provider: str) -> float:
        score = 100.0

        successes = len(self._successes.get(provider, []))
        failures = len(self._failures.get(provider, []))
        total = successes + failures
        if total == 0:
            return score

        error_rate = failures / total
        score -= error_rate * 50

        server_errors = sum(
            1 for f in self._failures.get(provider, [])
            if f.get("kind") in ("server_error", "overloaded", "timeout")
        )
        if server_errors > 0:
            score -= (server_errors / total) * 20

        latencies = list(self._latencies.get(provider, []))
        if len(latencies) >= 5:
            sorted_lat = sorted(latencies)
            p50 = sorted_lat[len(sorted_lat) // 2]
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
            if p50 > 0 and p95 > p50 * 2:
                ratio = p95 / p50
                score -= min(20.0, (ratio - 2.0) * 10.0)

        return max(0.0, min(100.0, score))

    def get_latency_p50(self, provider: str) -> float:
        latencies = list(self._latencies.get(provider, []))
        if not latencies:
            return 0.0
        sorted_lat = sorted(latencies)
        return sorted_lat[len(sorted_lat) // 2]

    def get_latency_p95(self, provider: str) -> float:
        latencies = list(self._latencies.get(provider, []))
        if not latencies:
            return 0.0
        sorted_lat = sorted(latencies)
        return sorted_lat[int(len(sorted_lat) * 0.95)]
