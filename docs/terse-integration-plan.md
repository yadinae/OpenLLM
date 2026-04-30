# 🧬 Terse + OpenLLM 集成方案

> **智能 Token 优化器** — 将 Terse 的 40-70% Token 压缩能力集成到 OpenLLM 网关

---

## 📊 项目对比

| 维度 | Terse | OpenLLM | 集成价值 |
|------|-------|---------|----------|
| **定位** | 客户端 Token 压缩器 | 服务端模型聚合网关 | 互补：客户端压缩 + 服务端路由 |
| **核心能力** | 7 阶段压缩管道 | 多协议适配 + 智能路由 | 压缩后的请求路由到最优模型 |
| **模型支持** | Claude/GPT 模式切换 | 10+ 模型提供商 | 按模型类型应用不同压缩策略 |
| **上下文管理** | 历史摘要 + 缓存感知 | Static/Dynamic/Reservoir/Adaptive | 增强上下文管理效率 |
| **成本优化** | 自动路由 (Opus→Sonnet) | 模型评分 + 故障转移 | 压缩 + 路由双重优化 |
| **部署方式** | macOS/iOS 客户端 | Python 服务端 | 可独立部署或组合使用 |

---

## 🏗️ 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Terse + OpenLLM 集成架构                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  客户端/Agent │───▶│  Terse 压缩层 │───▶│  OpenLLM 网关    │   │
│  │  (Claude Code │    │  (可选)       │    │  (服务端)        │   │
│  │   Cursor 等)  │    └──────────────┘    └────────┬─────────┘   │
│  └──────────────┘                                  │             │
│                                                     ▼             │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                  OpenLLM 增强网关                         │    │
│  │                                                          │    │
│  │  ┌────────────────────────────────────────────────────┐  │    │
│  │  │              API Router (/v1/*)                   │  │    │
│  │  └──────────────────────┬────────────────────────────┘  │    │
│  │                         │                                │    │
│  │  ┌──────────────────────▼────────────────────────────┐  │    │
│  │  │          Token Optimizer (新增)                   │  │    │
│  │  │  • 7 阶段压缩管道                                 │  │    │
│  │  │  • Git Diff 压缩                                  │  │    │
│  │  │  • 历史摘要                                       │  │    │
│  │  │  • 缓存感知                                       │  │    │
│  │  └──────────────────────┬────────────────────────────┘  │    │
│  │                         │                                │    │
│  │  ┌──────────────────────▼────────────────────────────┐  │    │
│  │  │          Model Dispatcher (增强)                  │  │    │
│  │  │  • 模型特定压缩策略                               │  │    │
│  │  │  • 自动路由 (Opus→Sonnet)                        │  │    │
│  │  │  • 重复工具调用检测                               │  │    │
│  │  └──────────────────────┬────────────────────────────┘  │    │
│  │                         │                                │    │
│  │  ┌──────────────────────▼────────────────────────────┐  │    │
│  │  │          Scorer Engine (增强)                     │  │    │
│  │  │  • Token 成本评分                                 │  │    │
│  │  │  • 压缩效率评分                                   │  │    │
│  │  └──────────────────────┬────────────────────────────┘  │    │
│  │                         │                                │    │
│  │  ┌──────────────────────▼────────────────────────────┐  │    │
│  │  │       Protocol Adapters (现有)                    │  │    │
│  │  │  ┌──────────┬──────────┬──────────┬──────────┐   │    │
│  │  │  │  OpenAI  │Anthropic │   REST   │  Ollama  │   │    │
│  │  │  └──────────┴──────────┴──────────┴──────────┘   │    │
│  │  └──────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 集成方案详解

### 方案 1：Token Optimizer 中间件（推荐）

在 OpenLLM 的 API Router 和 Model Dispatcher 之间添加 **Token Optimizer 中间件**。

#### 1.1 新增模块：`src/token_optimizer.py`

```python
class TokenOptimizer:
    """Terse 风格的 Token 优化器"""
    
    def __init__(self, mode: str = "normal"):
        """
        优化模式:
        - soft: 仅拼写修正 + 空白规范化
        - normal: 去除填充词 + 模式优化 + 冗余消除
        - aggressive: 最大压缩 + 电报风格
        """
        self.mode = mode
        self.pipeline = self._build_pipeline()
    
    def _build_pipeline(self) -> List[Callable]:
        """构建 7 阶段压缩管道"""
        stages = {
            "soft": [
                self.spell_correction,
                self.whitespace_normalization,
            ],
            "normal": [
                self.spell_correction,
                self.whitespace_normalization,
                self.pattern_optimization,
                self.redundancy_elimination,
            ],
            "aggressive": [
                self.spell_correction,
                self.whitespace_normalization,
                self.pattern_optimization,
                self.redundancy_elimination,
                self.nlp_analysis,
                self.telegraph_compression,
                self.final_cleanup,
            ]
        }
        return stages.get(self.mode, stages["normal"])
    
    def optimize(self, prompt: str, model: str = None) -> OptimizedPrompt:
        """执行优化管道"""
        original_tokens = self.count_tokens(prompt)
        optimized = prompt
        
        for stage in self.pipeline:
            optimized = stage(optimized)
        
        optimized_tokens = self.count_tokens(optimized)
        savings = original_tokens - optimized_tokens
        
        return OptimizedPrompt(
            original=prompt,
            optimized=optimized,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            savings=savings,
            savings_pct=savings / original_tokens if original_tokens > 0 else 0
        )
```

#### 1.2 集成到 Server

```python
# src/server.py
from .token_optimizer import TokenOptimizer

class OpenLLMServer:
    def __init__(self):
        self.optimizer = TokenOptimizer(mode="normal")
        # ... 现有代码
    
    async def chat_completions(self, request: ChatCompletionRequest):
        # 1. 优化用户消息
        for msg in request.messages:
            if msg.role == "user":
                optimized = self.optimizer.optimize(msg.content)
                msg.content = optimized.optimized
                # 记录优化效果
                self.metrics.record_optimization(optimized)
        
        # 2. 继续现有路由逻辑
        return await self.dispatcher.route(request)
```

---

### 方案 2：模型特定压缩策略

利用 OpenLLM 的 **Model Registry**，为不同模型应用不同压缩策略。

#### 2.1 模型配置扩展

```yaml
# config/models.yaml
models:
  - name: "anthropic/claude-opus-4"
    protocol: "anthropic"
    # Terse 压缩配置
    compression:
      mode: "aggressive"  # Claude 支持激进压缩
      preserve_structure: false  # 不需要保留显式结构
      max_compression_ratio: 0.7  # 最大压缩 70%
    
  - name: "openai/gpt-4o"
    protocol: "openai"
    compression:
      mode: "normal"  # GPT 需要保留结构
      preserve_structure: true
      max_compression_ratio: 0.5
    
  - name: "groq/llama-3.3-70b"
    protocol: "openai"
    compression:
      mode: "soft"  # 开源模型保守压缩
      preserve_structure: true
      max_compression_ratio: 0.3
```

#### 2.2 压缩策略选择器

```python
class CompressionStrategySelector:
    """根据模型选择压缩策略"""
    
    def get_strategy(self, model_name: str) -> CompressionConfig:
        model = self.registry.get_model(model_name)
        if not model:
            return CompressionConfig(mode="normal")
        
        # 基于模型特性选择策略
        if "claude" in model_name.lower():
            return CompressionConfig(
                mode="aggressive",
                preserve_structure=False,
                # Claude 擅长隐式推理，可激进压缩
            )
        elif "gpt" in model_name.lower():
            return CompressionConfig(
                mode="normal",
                preserve_structure=True,
                # GPT 需要显式指令，保留结构
            )
        else:
            return CompressionConfig(
                mode="soft",
                preserve_structure=True,
                # 开源模型保守处理
            )
```

---

### 方案 3：自动模型路由（Terse Proxy 功能）

实现 Terse 的 **Opus→Sonnet 自动路由**功能。

#### 3.1 复杂度评分器

```python
class ComplexityScorer:
    """评估请求复杂度，决定路由目标"""
    
    def score(self, messages: List[Message]) -> ComplexityScore:
        score = 0
        
        # 1. 提示词长度
        total_tokens = sum(self.count_tokens(m.content) for m in messages)
        if total_tokens < 100:
            score += 2  # 短提示词 → 简单
        elif total_tokens < 500:
            score += 1
        
        # 2. 任务类型检测
        content = " ".join(m.content for m in messages if m.role == "user")
        
        # 简单任务关键词
        simple_patterns = [
            r'lookup', r'search', r'find', r'check',  # 查找类
            r'edit', r'replace', r'fix', r'update',   # 编辑类
            r'what is', r'how to', r'explain',        # 解释类
        ]
        for pattern in simple_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 2
        
        # 复杂任务关键词
        complex_patterns = [
            r'architect', r'refactor', r'redesign',    # 架构类
            r'security', r'audit', r'review',          # 安全类
            r'optimize', r'performance',               # 优化类
        ]
        for pattern in complex_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 2
        
        # 3. 上下文长度
        context_tokens = self.get_context_tokens()
        if context_tokens > 50000:
            score -= 1  # 长上下文 → 复杂
        
        return ComplexityScore(
            score=score,
            is_simple=score >= 3,
            recommended_model=self._recommend_model(score)
        )
    
    def _recommend_model(self, score: int) -> str:
        """根据复杂度推荐模型"""
        if score >= 4:
            return "sonnet"  # 简单任务 → Sonnet ($3/MTok)
        elif score >= 2:
            return "opus"    # 中等任务 → Opus ($15/MTok)
        else:
            return "opus"    # 复杂任务 → Opus
```

#### 3.2 集成到 Dispatcher

```python
class ModelDispatcher:
    def route(self, request: ChatCompletionRequest):
        # 1. 计算复杂度
        scorer = ComplexityScorer()
        complexity = scorer.score(request.messages)
        
        # 2. 如果请求未指定模型，自动路由
        if request.model == "meta-model":
            request.model = complexity.recommended_model
        
        # 3. 继续现有路由逻辑
        return super().route(request)
```

---

### 方案 4：增强上下文管理

结合 Terse 的 **历史摘要** 和 **缓存感知** 技术，增强 OpenLLM 的上下文管理。

#### 4.1 历史摘要器

```python
class HistorySummarizer:
    """自动摘要长对话历史"""
    
    def summarize(self, messages: List[Message], max_tokens: int = 4000) -> List[Message]:
        current_tokens = sum(self.count_tokens(m.content) for m in messages)
        
        if current_tokens <= max_tokens:
            return messages  # 不需要摘要
        
        # 保留最近的消息
        recent_messages = []
        accumulated_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = self.count_tokens(msg.content)
            if accumulated_tokens + msg_tokens > max_tokens * 0.6:
                break
            recent_messages.append(msg)
            accumulated_tokens += msg_tokens
        
        # 摘要旧消息
        old_messages = messages[:-len(recent_messages)]
        if old_messages:
            summary = self._generate_summary(old_messages)
            recent_messages.append(Message(
                role="system",
                content=f"[Earlier conversation summarized]: {summary}"
            ))
        
        return list(reversed(recent_messages))
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """生成对话摘要"""
        # 简化版：提取关键信息
        user_msgs = [m.content for m in messages if m.role == "user"]
        assistant_msgs = [m.content for m in messages if m.role == "assistant"]
        
        summary_parts = []
        for user, assistant in zip(user_msgs[:3], assistant_msgs[:3]):
            # 提取关键动作和结论
            key_actions = self._extract_key_actions(user)
            key_conclusions = self._extract_key_conclusions(assistant)
            summary_parts.append(f"User: {key_actions} → Assistant: {key_conclusions}")
        
        return " | ".join(summary_parts)
```

#### 4.2 缓存感知器

```python
class CacheAwareness:
    """检测可缓存的内容块"""
    
    def __init__(self):
        self.cache_registry = {}  # 内容哈希 → 缓存 ID
    
    def analyze(self, messages: List[Message]) -> CacheAnalysis:
        """分析消息中的可缓存内容"""
        cacheable_blocks = []
        
        for i, msg in enumerate(messages):
            # 检测系统提示词
            if msg.role == "system":
                cacheable_blocks.append(CacheBlock(
                    index=i,
                    content=msg.content,
                    type="system_prompt",
                    cache_priority="high"
                ))
            
            # 检测重复内容
            content_hash = hashlib.md5(msg.content.encode()).hexdigest()
            if content_hash in self.cache_registry:
                cacheable_blocks.append(CacheBlock(
                    index=i,
                    content=msg.content,
                    type="duplicate",
                    cache_priority="medium",
                    original_index=self.cache_registry[content_hash]
                ))
            else:
                self.cache_registry[content_hash] = i
        
        return CacheAnalysis(
            cacheable_blocks=cacheable_blocks,
            potential_savings=sum(b.estimate_tokens() for b in cacheable_blocks),
            cache_hit_rate=len(cacheable_blocks) / len(messages) if messages else 0
        )
```

---

### 方案 5：Token 监控和报告

实现 Terse 的 **Agent Monitor** 功能。

#### 5.1 Token 监控器

```python
class TokenMonitor:
    """实时 Token 监控"""
    
    def __init__(self):
        self.sessions = {}  # session_id → SessionStats
    
    def record_request(self, session_id: str, request: dict, response: dict):
        """记录请求/响应统计"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionStats()
        
        session = self.sessions[session_id]
        session.turns += 1
        session.input_tokens += request.get("usage", {}).get("prompt_tokens", 0)
        session.output_tokens += request.get("usage", {}).get("completion_tokens", 0)
        session.cache_tokens += response.get("usage", {}).get("cache_tokens", 0)
        session.cost += self.calculate_cost(request, response)
    
    def get_session_stats(self, session_id: str) -> SessionStats:
        return self.sessions.get(session_id)
    
    def detect_anomalies(self, session_id: str) -> List[Anomaly]:
        """检测异常模式"""
        session = self.sessions.get(session_id)
        if not session:
            return []
        
        anomalies = []
        
        # 检测重复工具调用
        if session.duplicate_tool_calls > 3:
            anomalies.append(Anomaly(
                type="duplicate_tool_calls",
                severity="warning",
                message=f"检测到 {session.duplicate_tool_calls} 次重复工具调用"
            ))
        
        # 检测上下文填充率
        fill_rate = session.input_tokens / session.max_context
        if fill_rate > 0.85:
            anomalies.append(Anomaly(
                type="context_overflow",
                severity="critical",
                message=f"上下文填充率 {fill_rate*100:.0f}%，接近限制"
            ))
        
        return anomalies
```

---

## 📁 推荐文件结构

```
OpenLLM/
├── src/
│   ├── server.py              # 现有：API 服务器
│   ├── dispatcher.py          # 现有：模型调度器
│   ├── scorer.py              # 现有：模型评分器
│   ├── router.py              # 现有：路由选择器
│   ├── context.py             # 现有：上下文管理
│   ├── limiter.py             # 现有：速率限制器
│   ├── registry.py            # 现有：模型注册表
│   ├── freeride.py            # 现有：FreeRide 模式
│   │
│   │  # 新增 Terse 集成模块
│   ├── token_optimizer.py     # 🆕 Token 优化器（7 阶段管道）
│   ├── compression_strategy.py # 🆕 压缩策略选择器
│   ├── complexity_scorer.py   # 🆕 请求复杂度评分器
│   ├── history_summarizer.py  # 🆕 对话历史摘要器
│   ├── cache_awareness.py     # 🆕 缓存感知器
│   ├── token_monitor.py       # 🆕 Token 监控器
│   ├── git_diff_compressor.py # 🆕 Git Diff 压缩器
│   └── adapters/              # 现有：协议适配器
│
├── config/
│   ├── models.yaml            # 现有：模型配置（扩展 compression 字段）
│   └── compression.yaml       # 🆕 压缩配置
│
├── tests/
│   ├── test_token_optimizer.py    # 🆕 优化器测试
│   ├── test_compression.py        # 🆕 压缩策略测试
│   ├── test_complexity_scorer.py  # 🆕 复杂度评分测试
│   └── test_history_summarizer.py # 🆕 历史摘要测试
│
└── docs/
    ├── compression-guide.md   # 🆕 压缩功能文档
    └── token-monitoring.md    # 🆕 Token 监控文档
```

---

## 🚀 实施路线图

### 阶段 1：核心压缩（2 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 实现 7 阶段压缩管道 | `src/token_optimizer.py` | 3 天 |
| 集成到 API 请求流程 | `src/server.py` | 1 天 |
| 添加压缩配置 | `config/compression.yaml` | 0.5 天 |
| 编写测试用例 | `tests/test_token_optimizer.py` | 2 天 |
| 文档更新 | `docs/compression-guide.md` | 0.5 天 |

**预期效果**：40-60% Token 压缩率

### 阶段 2：模型特定策略（1 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 实现压缩策略选择器 | `src/compression_strategy.py` | 2 天 |
| 扩展模型配置格式 | `config/models.yaml` | 0.5 天 |
| 集成到 Dispatcher | `src/dispatcher.py` | 1 天 |
| 测试不同模型压缩效果 | `tests/test_compression.py` | 1.5 天 |

**预期效果**：Claude 70%、GPT 50%、开源模型 30%

### 阶段 3：自动路由（1 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 实现复杂度评分器 | `src/complexity_scorer.py` | 2 天 |
| 集成到路由选择 | `src/router.py` | 1 天 |
| 添加路由配置 | `config/models.yaml` | 0.5 天 |
| 测试路由效果 | `tests/test_complexity_scorer.py` | 1.5 天 |

**预期效果**：简单任务自动路由到便宜模型，成本降低 80%

### 阶段 4：上下文增强（1 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 实现历史摘要器 | `src/history_summarizer.py` | 2 天 |
| 实现缓存感知器 | `src/cache_awareness.py` | 2 天 |
| 集成到 Context Manager | `src/context.py` | 1 天 |

**预期效果**：历史上下文 80% 压缩，缓存命中率提升 50%

### 阶段 5：监控和报告（1 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 实现 Token 监控器 | `src/token_monitor.py` | 2 天 |
| 添加监控 API | `src/server.py` | 1 天 |
| 实现 Git Diff 压缩 | `src/git_diff_compressor.py` | 2 天 |

**预期效果**：实时 Token 跟踪，异常检测，Git Diff 70% 压缩

---

## 📊 预期效果

| 指标 | 当前 OpenLLM | 集成 Terse 后 | 提升 |
|------|-------------|--------------|------|
| **输入 Token 数** | 原始 | 压缩 40-70% | ⬇️ 60% |
| **API 成本** | 按模型定价 | 压缩 + 自动路由 | ⬇️ 70% |
| **上下文利用率** | 静态/动态 | 摘要 + 缓存感知 | ⬆️ 50% |
| **重复调用检测** | 无 | 自动检测 + 警告 | ✅ 新增 |
| **Token 可见性** | 基础统计 | 实时跟踪 + 异常检测 | ⬆️ 100% |

---

## 🔒 安全和隐私

- **100% 本地处理**：压缩在 OpenLLM 服务端完成，不依赖外部 API
- **代码保护**：反引号内的代码块、URL、内联代码不受压缩影响
- **可配置**：用户可选择压缩模式和强度
- **透明**：所有压缩操作可追溯，原始内容保留用于审计

---

## 📝 总结

Terse 和 OpenLLM 的集成将创建一个 **完整的 Token 优化解决方案**：

1. **客户端压缩**（Terse）→ **服务端压缩**（OpenLLM）
2. **模型特定策略** → 最大化压缩效果
3. **自动路由** → 最小化 API 成本
4. **上下文增强** → 最大化上下文利用率
5. **实时监控** → 可见性和控制

这种集成将使 OpenLLM 成为 **市场上最高效的 AI 模型聚合网关**。
