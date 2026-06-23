"""电路熔断器 (Circuit Breaker) — Provider 健康状态追踪

跟踪每个 Provider 的连续失败次数，在阈值超标时自动触发熔断。
熔断后请求在熔断期内被快速拒绝，避免对故障 Provider 的不必要调用。

安全设计：
- 状态表使用 LRU 机制，最多跟踪 MAX_KEYS 个 key
- record_success 自动清理 CLOSED 状态的条目
- 防止用户可控的 provider_name 导致内存耗尽
"""

from __future__ import annotations

import time
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Provider 熔断器

    状态机: CLOSED (正常) → OPEN (熔断中) → HALF_OPEN (试探) → CLOSED

    用法:
        cb = CircuitBreaker()
        cb.record_success("groq")    # 复位
        cb.record_failure("groq")    # 增加失败计数
        if cb.is_open("groq"):
            print("groq 熔断中，跳过")
    """

    FAILURE_THRESHOLD = 5       # 连续失败 N 次后熔断
    OPEN_TIMEOUT = 60.0         # 熔断持续时间（秒）
    HALF_OPEN_SUCCESS = 3       # 半开状态需要连续成功 N 次才恢复
    MAX_KEYS = 100              # 状态表最大 key 数（防内存耗尽）

    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._states: dict[str, tuple[str, float]] = {}
        self._half_open_successes: dict[str, int] = {}
        self._access_order: OrderedDict[str, None] = OrderedDict()

    def _touch(self, name: str) -> None:
        """更新 LRU 访问顺序

        只跟踪已被 _states 或 _failures 记录的 key。
        已淘汰的 key 不会重新加入（防止无限增长）。
        """
        if name in self._states or name in self._failures:
            self._access_order[name] = None
            self._access_order.move_to_end(name)
        # 超限时淘汰最久未使用的 key
        while len(self._access_order) > self.MAX_KEYS:
            oldest = next(iter(self._access_order))
            self._access_order.pop(oldest)
            self._failures.pop(oldest, None)
            self._states.pop(oldest, None)
            self._half_open_successes.pop(oldest, None)

    def _cleanup(self, name: str) -> None:
        """清理 CLOSED 状态的条目"""
        state, _ = self._states.get(name, ("CLOSED", 0))
        if state == "CLOSED":
            self._failures.pop(name, None)
            self._half_open_successes.pop(name, None)
            self._access_order.pop(name, None)

    def record_success(self, name: str) -> None:
        """记录成功调用 — 复位失败计数"""
        self._failures.pop(name, None)
        self._touch(name)
        # 如果在 HALF_OPEN 状态，计数成功
        state, until = self._states.get(name, ("CLOSED", 0))
        if state == "HALF_OPEN":
            successes = self._half_open_successes.get(name, 0) + 1
            self._half_open_successes[name] = successes
            if successes >= self.HALF_OPEN_SUCCESS:
                del self._states[name]
                del self._half_open_successes[name]
                self._cleanup(name)
                logger.info("Circuit breaker %s: HALF_OPEN → CLOSED (recovered)", name)
        elif state != "CLOSED":
            # 在 OPEN 状态收到成功？不可能，恢复
            self._states.pop(name, None)
            self._cleanup(name)

    def record_failure(self, name: str) -> bool:
        """记录失败调用 — 返回是否刚触发了熔断"""
        failures = self._failures.get(name, 0) + 1
        self._failures[name] = failures
        self._touch(name)

        if failures >= self.FAILURE_THRESHOLD:
            state, until = self._states.get(name, ("CLOSED", 0))
            if state != "OPEN":
                self._states[name] = ("OPEN", time.time() + self.OPEN_TIMEOUT)
                self._half_open_successes.pop(name, None)
                logger.warning(
                    "Circuit breaker %s: → OPEN (%d consecutive failures)",
                    name, failures,
                )
                return True  # 刚触发熔断
        return False

    def is_open(self, name: str) -> bool:
        """检查是否处于熔断状态"""
        state, until = self._states.get(name, ("CLOSED", 0))
        if name in self._states:
            self._touch(name)
        if state == "CLOSED":
            return False
        if state == "OPEN" and time.time() >= until:
            # 熔断时间到 → 转为 HALF_OPEN 允许试探
            self._states[name] = ("HALF_OPEN", 0)
            logger.info("Circuit breaker %s: OPEN → HALF_OPEN (timeout expired)", name)
            return False
        if state == "HALF_OPEN":
            return False  # 允许试探请求
        return True

    def get_state(self, name: str) -> dict:
        """获取 provider 的熔断器完整状态"""
        state, until = self._states.get(name, ("CLOSED", 0))
        if name in self._states:
            self._touch(name)
        return {
            "state": state,
            "failures": self._failures.get(name, 0),
            "remaining": self.get_remaining(name),
            "half_open_successes": self._half_open_successes.get(name, 0),
        }

    def get_remaining(self, name: str) -> float:
        """获取熔断剩余时间（秒）"""
        state, until = self._states.get(name, ("CLOSED", 0))
        if state == "OPEN":
            remaining = until - time.time()
            return max(0.0, remaining)
        return 0.0

    def reset(self, name: str | None = None) -> None:
        """手动复位熔断器"""
        if name:
            self._failures.pop(name, None)
            self._states.pop(name, None)
            self._half_open_successes.pop(name, None)
            self._access_order.pop(name, None)
        else:
            self._failures.clear()
            self._states.clear()
            self._half_open_successes.clear()
            self._access_order.clear()
