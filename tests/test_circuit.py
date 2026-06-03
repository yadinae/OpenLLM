"""电路熔断器单元测试"""
from __future__ import annotations


from openllm.core.circuit import CircuitBreaker


class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker()

    def test_initial_state_closed(self):
        assert not self.cb.is_open("groq")
        assert self.cb.get_remaining("groq") == 0.0

    def test_success_resets_failure_count(self):
        self.cb.record_failure("groq")
        self.cb.record_failure("groq")
        self.cb.record_success("groq")
        assert not self.cb.is_open("groq")

    def test_opens_after_threshold_failures(self):
        for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
            self.cb.record_failure("groq")
        assert self.cb.is_open("groq")

    def test_get_remaining_non_zero_when_open(self):
        for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
            self.cb.record_failure("groq")
        assert self.cb.get_remaining("groq") > 0.0

    def test_reset_clears_state(self):
        for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
            self.cb.record_failure("groq")
        assert self.cb.is_open("groq")
        self.cb.reset("groq")
        assert not self.cb.is_open("groq")

    def test_reset_all_clears_everything(self):
        self.cb.record_failure("a")
        self.cb.record_failure("b")
        self.cb.reset()
        assert not self.cb.is_open("a")
        assert not self.cb.is_open("b")

    def test_lru_eviction_oldest_key(self):
        """超过 MAX_KEYS 时淘汰最久未使用的 key"""
        for i in range(CircuitBreaker.MAX_KEYS + 10):
            for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
                self.cb.record_failure(f"p{i}")
        # 前 10 个 key 应该已被淘汰
        assert not self.cb.is_open("p0"), "LRU should evict oldest key"
        # 后 10 个 key 应该还在
        assert self.cb.is_open(f"p{CircuitBreaker.MAX_KEYS + 9}")

    def test_lru_touch_prevents_eviction(self):
        """访问过的 key 不会被淘汰"""
        for i in range(CircuitBreaker.MAX_KEYS):
            for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
                self.cb.record_failure(f"p{i}")
        # 重新访问 p0
        self.cb.is_open("p0")
        # 再添加新 key（5 次失败触发熔断）
        for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
            self.cb.record_failure("new")
        # p0 应该还在（刚被 touch 过）
        assert self.cb.is_open("p0")
        assert self.cb._failures.get("p0", 0) >= CircuitBreaker.FAILURE_THRESHOLD

    def test_cleanup_after_recovery(self):
        """从 HALF_OPEN 恢复后自动清理"""
        for _ in range(CircuitBreaker.FAILURE_THRESHOLD):
            self.cb.record_failure("p")
        assert self.cb.is_open("p")
        # 模拟 HALF_OPEN: 跳到 OPEN 超时后
        self.cb._states["p"] = ("HALF_OPEN", 0)
        for _ in range(CircuitBreaker.HALF_OPEN_SUCCESS):
            self.cb.record_success("p")
        # 恢复后状态表应不含 p
        assert "p" not in self.cb._states
