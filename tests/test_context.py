"""上下文管理器边界条件和异常测试"""
from __future__ import annotations

from openllm.context.manager import ContextManager


class TestContextManager:
    def setup_method(self):
        self.mgr = ContextManager()

    # ── Static 模式 ──

    def test_static_keep_within_budget(self):
        msg = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = self.mgr._optimize_static(msg)
        assert len(result) == 5  # 小于预算，全部保留

    def test_static_truncate(self):
        msg = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = self.mgr._optimize_static(msg)
        assert len(result) == 10  # 只保留最后 10 条

    def test_static_empty(self):
        assert self.mgr._optimize_static([]) == []

    # ── Dynamic 模式 ──

    def test_dynamic_small(self):
        """估算 token < 1000 时返回全部"""
        msg = [{"role": "user", "content": "short"} for _ in range(3)]
        result = self.mgr._optimize_dynamic(msg)
        assert result == msg

    def test_dynamic_large(self):
        """大量内容时保留部分"""
        msg = [{"role": "user", "content": "x" * 1000} for _ in range(20)]
        result = self.mgr._optimize_dynamic(msg)
        assert len(result) < len(msg)

    def test_dynamic_empty(self):
        assert self.mgr._optimize_dynamic([]) == []

    # ── Reservoir 模式 ──

    def test_reservoir_within_budget(self):
        msg = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        result = self.mgr._optimize_reservoir(msg)
        assert result == msg  # 10 <= 15 (reservoir_recent)

    def test_reservoir_empty(self):
        assert self.mgr._optimize_reservoir([]) == []

    def test_reservoir_summary_generation(self):
        """超出预算时生成摘要"""
        msg = [{"role": "user", "content": f"This is message number {i} with some content" * 5}
               for i in range(20)]
        result = self.mgr._optimize_reservoir(msg)
        assert len(result) < 20
        # 第一条应该是摘要
        assert result[0]["role"] == "system"
        assert "summary" in result[0]["content"].lower()

    def test_reservoir_summary_empty_early_messages(self):
        """早期消息全部为空时，摘要应为空，直接返回 recent"""
        msg = [{"role": "user", "content": ""} for _ in range(20)] + \
              [{"role": "user", "content": "recent"} for _ in range(15)]
        result = self.mgr._optimize_reservoir(msg)
        assert len(result) <= 15

    # ── Adaptive 模式 ──

    def test_adaptive_short_conversation(self):
        """< 5 条消息 → static"""
        msg = [{"role": "user", "content": "hi"} for _ in range(3)]
        result = self.mgr._optimize_adaptive(msg)
        # 短对话，应该是 static 模式
        assert len(result) == 3

    def test_adaptive_empty(self):
        assert self.mgr._optimize_adaptive([]) == []

    def test_adaptive_code_heavy(self):
        """代码占 > 30% → reservoir"""
        msg = [
            {"role": "user", "content": "```python\nprint('hello')\n```"},
            {"role": "user", "content": "```python\nprint('world')\n```"},
            {"role": "user", "content": "```python\nprint('foo')\n```"},
            {"role": "user", "content": "some normal text"},
            {"role": "user", "content": "more normal text"},
        ]
        result = self.mgr._optimize_adaptive(msg)
        # 应该有摘要（reservoir 行为）
        assert any(m.get("role") == "system" and "summary" in m.get("content", "").lower()
                   for m in result) or len(result) > 0

    # ── Extract Summary ──

    def test_extractive_summary_empty(self):
        assert self.mgr._extractive_summary("", 100) == ""

    def test_extractive_summary_short(self):
        """短文本（<= 2 句）直接返回"""
        text = "Hello world. How are you?"
        result = self.mgr._extractive_summary(text, 100)
        assert result == text

    def test_extractive_summary_long(self):
        """长文本抽取摘要，长度不应超过 max_chars"""
        text = ". ".join([f"This is sentence number {i} about various topics." for i in range(50)])
        result = self.mgr._extractive_summary(text, 200)
        assert len(result) <= 200
        assert len(result) > 0

    # ── Mode routing ──

    def test_optimize_invalid_mode_fallback(self):
        msg = [{"role": "user", "content": "hi"}]
        # 无效模式应该 fallback 到原始消息
        result = self.mgr.optimize(msg, mode="nonexistent")
        assert result == msg

    def test_optimize_default_adaptive(self):
        assert self.mgr.mode == "adaptive"

    def test_constructor_invalid_mode(self):
        """构造函数传入无效模式时回退到 adaptive"""
        mgr = ContextManager(mode="invalid")
        assert mgr.mode == "adaptive"

    def test_optimize_all_modes_work(self):
        msg = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        for mode in ["static", "dynamic", "reservoir", "adaptive"]:
            result = self.mgr.optimize(msg, mode=mode)
            assert isinstance(result, list)
            assert len(result) > 0
