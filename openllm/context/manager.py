"""上下文管理器 — 多模式对话上下文优化（参考 RelayFreeLLM 设计）

4 种模式：
- Static:    保留最后 N 条消息
- Dynamic:   根据 token 使用率动态调整窗口
- Reservoir: 最近消息保留 + 早期历史抽取摘要
- Adaptive:  自动检测对话类型选择最佳模式
"""

from __future__ import annotations

import re
from collections import Counter


class ContextManager:
    """多模式上下文管理器"""
    
    MODES = ["static", "dynamic", "reservoir", "adaptive"]
    
    def __init__(self, mode: str = "adaptive"):
        self.mode = mode if mode in self.MODES else "adaptive"
        self.static_keep = 10
        self.reservoir_recent = 15
        self.summary_budget = 400  # 摘要最大字符数
        self.utilization_target = 0.8
    
    def optimize(self, messages: list[dict], mode: str | None = None) -> list[dict]:
        """优化消息列表
        
        Args:
            messages: [{"role": str, "content": str}, ...]
            mode: 覆盖当前模式
        
        Returns:
            优化后的消息列表
        """
        _mode = mode or self.mode
        
        if _mode == "static":
            return self._optimize_static(messages)
        elif _mode == "dynamic":
            return self._optimize_dynamic(messages)
        elif _mode == "reservoir":
            return self._optimize_reservoir(messages)
        elif _mode == "adaptive":
            return self._optimize_adaptive(messages)
        return messages
    
    def _optimize_static(self, messages: list[dict]) -> list[dict]:
        """Static 模式 — 保留最后 N 条"""
        if len(messages) <= self.static_keep:
            return messages
        return messages[-self.static_keep:]
    
    def _optimize_dynamic(self, messages: list[dict]) -> list[dict]:
        """Dynamic 模式 — 根据 token 估算动态调整"""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        # 粗估: 1 token ≈ 4 chars
        est_tokens = total_chars / 4
        
        if est_tokens < 1000:
            return messages
        
        # 按利用率调整保留比例
        ratio = min(1.0, self.utilization_target * 4000 / max(est_tokens, 1))
        keep = max(int(len(messages) * ratio), 3)
        return messages[-keep:]
    
    def _optimize_reservoir(self, messages: list[dict]) -> list[dict]:
        """Reservoir 模式 — 最近保留 + 早期摘要
        
        保留最近 N 条完整消息，早期消息用抽取式摘要替代。
        不需要 LLM 调用，使用 TF 评分提取关键句。
        """
        if len(messages) <= self.reservoir_recent:
            return messages
        
        recent = messages[-self.reservoir_recent:]
        early = messages[:-self.reservoir_recent]
        
        # 抽取早期消息摘要
        early_text = "\n".join(m.get("content", "") for m in early if m.get("content"))
        summary = self._extractive_summary(early_text, self.summary_budget)
        
        if summary:
            return [{"role": "system", "content": f"[Earlier conversation summary]: {summary}"}] + recent
        return recent
    
    def _optimize_adaptive(self, messages: list[dict]) -> list[dict]:
        """Adaptive 模式 — 自动检测对话类型
        
        - 代码密集 → Reservoir
        - 长对话 → Dynamic
        - 简短对话 → Static
        """
        if len(messages) < 5:
            return self._optimize_static(messages)
        
        # 检测代码密集度
        total_text = " ".join(m.get("content", "") for m in messages)
        code_pattern = re.findall(r"```[\s\S]*?```", total_text)
        code_ratio = sum(len(c) for c in code_pattern) / max(len(total_text), 1)
        
        if code_ratio > 0.3:
            return self._optimize_reservoir(messages)
        
        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars > 5000:
            return self._optimize_dynamic(messages)
        
        return self._optimize_static(messages)
    
    def _extractive_summary(self, text: str, max_chars: int) -> str:
        """抽取式摘要 — 无 LLM，纯统计方法
        
        1. 分句
        2. TF (词频) 评分
        3. 位置加权
        4. 选出高价值句子至 max_chars
        """
        if not text:
            return ""
        
        # 简单分句
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 2:
            return text[:max_chars]
        
        # 词频统计
        words = re.findall(r"\w+", text.lower())
        word_freq = Counter(words)
        
        # 句子评分: 词频和 + 位置权重
        scored = []
        for i, sent in enumerate(sentences):
            if len(sent) < 10:
                continue
            sent_words = re.findall(r"\w+", sent.lower())
            freq_score = sum(word_freq.get(w, 0) for w in sent_words) / max(len(sent_words), 1)
            position_weight = 1.0 + (1.0 - i / len(sentences))  # 越早权重越高
            scored.append((freq_score * position_weight, sent))
        
        # 按评分排序，选取高价值句子
        scored.sort(reverse=True)
        result = []
        char_count = 0
        for _, sent in scored:
            if char_count + len(sent) > max_chars:
                break
            result.append(sent)
            char_count += len(sent)
        
        # 按原文顺序重排
        ordered = [s for s in sentences if s in result]
        return " ".join(ordered) if ordered else text[:max_chars]
