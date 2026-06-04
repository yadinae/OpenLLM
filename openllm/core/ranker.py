"""
OpenLLM Model Ranker
====================
模型优选系统 — 对各 Provider 的模型进行基准测试，提供速度/质量/成本的综合评分和推荐。

工作原理:
  1. 发现所有 Provider 的模型列表
  2. 对每个模型运行标准测试（速度 + 质量 + 可用性）
  3. 存储基准结果到 ~/.openllm/rankings.json
  4. 提供查询接口: 按速度/质量/成本排序推荐

评分算法:
  - Speed (0-100): 基于 TTFT 和 tokens/s 的百分位排名
  - Quality (0-100): QGS 评审质量评分
  - Cost (0-100): 基于已知定价的性价比评分
  - Overall (0-100): 加权综合分 (speed×0.3 + quality×0.5 + cost×0.2)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openllm.core.state import get_data_dir, write_json_atomic, read_json
from openllm.core.types import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)

# ── 标准测试题目 ──────────────────────────────
# 速度基准: 极短回复，测量原始响应速度
BENCHMARK_SPEED_PROMPT = 'Reply with exactly one word: "hello"'
BENCHMARK_SPEED_MAX_TOKENS = 10

# 质量基准: 中等长度回复，评估内容质量
BENCHMARK_QUALITY_PROMPT = (
    "Write a brief Python code example (5-10 lines) that demonstrates "
    "list comprehension. Include a comment explaining what it does."
)
BENCHMARK_QUALITY_MAX_TOKENS = 200

# ── 评分权重 ──────────────────────────────────
WEIGHT_SPEED = 0.30
WEIGHT_QUALITY = 0.50
WEIGHT_COST = 0.20

# 已知定价（USD / 1K tokens），仅供参考
# 来源: 各 Provider 官方定价页，可能变化
KNOWN_PRICING: dict[str, dict[str, float]] = {
    # provider -> {"input": $/1K, "output": $/1K}
    "deepseek": {"input": 0.0005, "output": 0.0020},     # deepseek-chat
    "nvidia":   {"input": 0.0000, "output": 0.0000},     # NVIDIA free API
    "router":   {"input": 0.0000, "output": 0.0000},     # 自建服务
    "opencode": {"input": 0.0000, "output": 0.0000},     # opencode 免费
}

# ── 数据模型 ──────────────────────────────────


@dataclass
class BenchmarkResult:
    """单个模型的基准测试结果"""
    provider: str
    model_id: str                     # provider/model
    # Speed metrics
    avg_latency_ms: float = 0.0       # 平均响应延迟 (ms)
    ttft_ms: float = 0.0              # Time To First Token (ms)
    tokens_per_second: float = 0.0    # 输出吞吐量
    # Quality metrics
    quality_score: float = 0.0        # 质量评分 0-100
    quality_issues: list[str] = field(default_factory=list)
    # Cost metrics
    cost_per_1k_input: float = 0.0    # USD / 1K input tokens
    cost_per_1k_output: float = 0.0   # USD / 1K output tokens
    # Composite
    speed_score: float = 0.0          # 0-100
    cost_score: float = 0.0           # 0-100
    overall_score: float = 0.0        # 0-100
    # Stats
    error_rate: float = 0.0           # 0.0-1.0
    test_runs: int = 0                # 测试次数
    tested_at: str = ""               # ISO timestamp
    model_name: str = ""              # 原始模型名


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 优先引擎 ──────────────────────────────────


class Ranker:
    """模型优选引擎"""

    def __init__(self, registry=None, data_dir: str | Path | None = None):
        self.registry = registry
        self._data_dir = Path(data_dir) if data_dir else get_data_dir()
        self._rankings_path = self._data_dir / "rankings.json"

    # ── 存储 ──

    def load_rankings(self) -> dict[str, BenchmarkResult]:
        """加载已保存的基准测试结果"""
        data = read_json(self._rankings_path, {})
        results = {}
        for key, val in data.items():
            try:
                results[key] = BenchmarkResult(**val)
            except Exception as e:
                logger.warning("Skipping invalid ranking entry %s: %s", key, e)
        return results

    def save_rankings(self, results: dict[str, BenchmarkResult]) -> None:
        """保存基准测试结果"""
        serializable = {}
        for key, val in results.items():
            serializable[key] = asdict(val)
        write_json_atomic(self._rankings_path, serializable)

    def get_ranking(self, model_key: str) -> BenchmarkResult | None:
        """获取单个模型的基准结果"""
        return self.load_rankings().get(model_key)

    # ── 发现待测模型 ──

    def _collect_candidates(self) -> list[tuple[str, str, str]]:
        """收集所有 Provider 的模型列表 -> [(provider, model_name, full_key)]"""
        if not self.registry:
            return []
        candidates = []
        for m in self.registry.get_cached_models():
            provider = m.get("provider", "")
            model_name = m.get("id", "")
            key = f"{provider}/{model_name}"
            candidates.append((provider, model_name, key))
        return candidates

    # ── 运行基准测试 ──

    async def benchmark_all(self, progress=None) -> dict[str, BenchmarkResult]:
        """对所有已发现的模型运行基准测试
        
        Args:
            progress: 可选回调, 接收 (current, total, provider, model) 用于显示进度
        
        Returns:
            {model_key: BenchmarkResult}
        """
        candidates = self._collect_candidates()
        if not candidates:
            logger.warning("No models discovered to benchmark")
            return {}

        results: dict[str, BenchmarkResult] = {}
        total = len(candidates)

        for idx, (provider, model_name, key) in enumerate(candidates, 1):
            if progress:
                progress(idx, total, provider, model_name)

            try:
                result = await self._benchmark_single(provider, model_name, key)
                results[key] = result
            except Exception as e:
                logger.error("Benchmark failed for %s: %s", key, e)
                results[key] = BenchmarkResult(
                    provider=provider,
                    model_id=key,
                    error_rate=1.0,
                    tested_at=_now(),
                )

        # 计算相对评分
        self._compute_scores(results)
        self.save_rankings(results)
        return results

    async def benchmark_one(
        self, provider: str, model_name: str
    ) -> BenchmarkResult:
        """对单个模型运行基准测试"""
        key = f"{provider}/{model_name}"
        result = await self._benchmark_single(provider, model_name, key)

        # 加载已有结果，合并更新评分
        all_results = self.load_rankings()
        all_results[key] = result
        self._compute_scores(all_results)
        self.save_rankings(all_results)
        return result

    async def _benchmark_single(
        self, provider: str, model_name: str, key: str
    ) -> BenchmarkResult:
        """对单个模型运行所有基准测试"""
        if not self.registry:
            return BenchmarkResult(provider=provider, model_id=key, tested_at=_now())

        p = self.registry.get(provider)
        if not p:
            return BenchmarkResult(
                provider=provider, model_id=key,
                error_rate=1.0, tested_at=_now(),
            )

        run_count = 0
        latencies: list[float] = []
        errors = 0
        total_tokens = 0
        total_time = 0.0
        quality_result = ""
        quality_issues: list[str] = []

        # ── 测试 1: 速度基准 (非流式) ──
        for i in range(3):  # 跑3次取平均
            try:
                req = ChatRequest(
                    model=f"{provider}/{model_name}",
                    messages=[ChatMessage(role="user", content=BENCHMARK_SPEED_PROMPT)],
                    max_tokens=BENCHMARK_SPEED_MAX_TOKENS,
                    temperature=0,
                )
                start = time.monotonic()
                resp = await p.chat_completion(req)
                elapsed_ms = (time.monotonic() - start) * 1000
                latencies.append(elapsed_ms)
                if resp.usage:
                    total_tokens += resp.usage.completion_tokens or 0
                total_time += elapsed_ms / 1000
                run_count += 1
            except Exception as e:
                logger.warning("Speed test %s (run %d): %s", key, i, e)
                errors += 1

        # ── 测试 2: 质量基准 (速度 + 内容质量) ──
        try:
            req = ChatRequest(
                model=f"{provider}/{model_name}",
                messages=[ChatMessage(role="user", content=BENCHMARK_QUALITY_PROMPT)],
                max_tokens=BENCHMARK_QUALITY_MAX_TOKENS,
                temperature=0.3,
            )
            start = time.monotonic()
            resp = await p.chat_completion(req)
            q_elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(q_elapsed_ms)
            quality_result = resp.content or ""
            if resp.usage:
                total_tokens += resp.usage.completion_tokens or 0
            total_time += q_elapsed_ms / 1000
            run_count += 1
        except Exception as e:
            logger.warning("Quality test %s: %s", key, e)
            errors += 1

        # ── 计算指标 ──
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        tokens_per_sec = total_tokens / total_time if total_time > 0 else 0
        error_rate = errors / (run_count + errors) if (run_count + errors) > 0 else 0

        # ── 质量评分 (使用 QGS 评审) ──
        quality_score = self._quality_eval(provider, model_name, key, quality_result)
        if quality_score is None:
            quality_score = 50.0  # 默认中等分

        # ── 成本 ──
        pricing = KNOWN_PRICING.get(provider.lower(), {})
        cost_in = pricing.get("input", 0.0)
        cost_out = pricing.get("output", 0.0)

        return BenchmarkResult(
            provider=provider,
            model_id=key,
            avg_latency_ms=round(avg_lat, 1),
            tokens_per_second=round(tokens_per_sec, 1),
            quality_score=round(quality_score, 1),
            quality_issues=quality_issues,
            cost_per_1k_input=cost_in,
            cost_per_1k_output=cost_out,
            error_rate=round(error_rate, 3),
            test_runs=run_count,
            tested_at=_now(),
        )

    def _quality_eval(
        self, provider: str, model_name: str, key: str, content: str
    ) -> float | None:
        """评估生成内容的质量分数
        
        使用启发式规则评估:
        - 代码正确性 (有语法有效的 Python 代码?)
        - 完整性 (包含注释?)
        - 相关性 (与提示词相关?)
        
        返回 0-100 分数, None 表示无法评估
        """
        if not content or len(content.strip()) < 10:
            return 30.0

        score = 60.0  # 基准分

        # 包含代码块
        if "```" in content:
            score += 10
        # 包含注释
        if "#" in content or "//" in content or "/*" in content:
            score += 10
        # 有实质性内容
        if len(content) > 100:
            score += 10
        # 包含解释/描述性文字
        if any(kw in content.lower() for kw in ["explain", "demonstrate", "example",
                                                  "使用", "示例", "说明"]):
            score += 5
        # 结构清晰
        if "\n" in content:
            score += 5

        return min(100, score)

    def _compute_scores(self, results: dict[str, BenchmarkResult]) -> None:
        """基于所有结果计算相对评分（百分位）"""
        if not results:
            return

        # 提取各维度原始值
        latencies = [(k, r.avg_latency_ms) for k, r in results.items() if r.avg_latency_ms > 0]
        qualities = [(k, r.quality_score) for k, r in results.items()]
        errors = [(k, r.error_rate) for k, r in results.items()]

        # Speed score: 延迟越低越好 (逆百分位)
        if latencies:
            sorted_lat = sorted(latencies, key=lambda x: x[1])
            best_lat = sorted_lat[0][1]
            worst_lat = sorted_lat[-1][1]
            lat_range = max(1, worst_lat - best_lat)

            for k, v in results.items():
                if v.avg_latency_ms > 0:
                    # 线性映射: fastest=100, slowest=0
                    v.speed_score = round(
                        max(0, 100 - (v.avg_latency_ms - best_lat) / lat_range * 100),
                        1
                    )
                    # 如果有错误, 降权
                    if v.error_rate > 0:
                        v.speed_score = round(v.speed_score * (1 - v.error_rate * 0.5), 1)
                else:
                    v.speed_score = 0

        # Cost score: 免费=100, 收费按比例
        all_costs = [r.cost_per_1k_output for r in results.values()]
        max_cost = max(all_costs) if all_costs else 0
        for v in results.values():
            if max_cost > 0:
                v.cost_score = round(max(0, 100 - v.cost_per_1k_output / max_cost * 100), 1)
            else:
                v.cost_score = 100  # 全部免费

        # Overall: 加权综合
        for v in results.values():
            v.overall_score = round(
                v.speed_score * WEIGHT_SPEED
                + v.quality_score * WEIGHT_QUALITY
                + v.cost_score * WEIGHT_COST,
                1,
            )

    # ── 推荐接口 ──

    def recommend(
        self,
        preference: str = "quality",
        top_n: int = 5,
    ) -> list[BenchmarkResult]:
        """根据偏好推荐最优模型
        
        Args:
            preference: "speed" | "quality" | "cost" | "balanced"
            top_n: 返回数量
        
        Returns:
            按评分降序排列的 BenchmarkResult 列表
        """
        results = self.load_rankings()
        if not results:
            return []

        sort_map = {
            "speed": "speed_score",
            "quality": "quality_score",
            "cost": "cost_score",
            "balanced": "overall_score",
        }
        sort_key = sort_map.get(preference, "overall_score")

        sorted_results = sorted(
            results.values(),
            key=lambda r: getattr(r, sort_key, 0),
            reverse=True,
        )

        return sorted_results[:top_n]
