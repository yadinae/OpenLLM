# Token Optimizer 使用指南

> OpenLLM 内置的 Terse 风格智能 Token 压缩器

---

## 📖 概述

Token Optimizer 是 OpenLLM 的内置 Token 压缩模块，基于 Terse 的 7 阶段压缩管道实现。它可以在不影响语义的前提下，将输入 Token 数量减少 40-70%。

### 核心特性

- **7 阶段压缩管道**：拼写修正 → 空白规范化 → 模式优化 → 冗余消除 → NLP 分析 → 电报压缩 → 最终清理
- **3 种压缩模式**：Soft / Normal / Aggressive
- **代码块保护**：反引号内的代码、URL、内联代码不受压缩影响
- **模型特定策略**：Claude 激进压缩 / GPT 保留结构 / 开源模型保守压缩
- **100% 本地处理**：零延迟，隐私安全

---

## 🚀 快速开始

### 基本用法

```python
from src.token_optimizer import TokenOptimizer, CompressionMode

# 创建优化器（默认 Normal 模式）
optimizer = TokenOptimizer()

# 优化单个提示词
result = optimizer.optimize("I don't know if this makes sense but could you maybe help me refactor the authentication module")
print(result)
# Output: OptimizedPrompt: 26→19 tok (27% saved, 7 tokens)

# 优化消息列表
messages = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "I don't know if this makes sense but could you maybe help me refactor the authentication module"},
]
optimized = optimizer.optimize_messages(messages)
```

### 压缩模式

| 模式 | 适用场景 | 压缩率 | 阶段 |
|------|----------|--------|------|
| **Soft** | 关键提示词、需要保留原始语义 | 5-15% | 拼写修正 + 空白规范化 |
| **Normal** | 日常对话、一般请求 | 20-50% | + 模式优化 + 冗余消除 |
| **Aggressive** | Agent 会话、内部工具调用 | 40-70% | + NLP 分析 + 电报压缩 + 最终清理 |

```python
# Soft 模式
optimizer = TokenOptimizer(mode=CompressionMode.SOFT)

# Normal 模式（默认）
optimizer = TokenOptimizer(mode=CompressionMode.NORMAL)

# Aggressive 模式
optimizer = TokenOptimizer(mode=CompressionMode.AGGRESSIVE)
```

---

## 🔧 配置

### 压缩配置 (`config/compression.yaml`)

```yaml
# 全局压缩模式
mode: normal

# 是否保护代码块
preserve_code: true

# 最大压缩率（0.7 = 最大 70%）
max_compression_ratio: 0.7

# 最小 Token 数（低于此值不压缩）
min_tokens_to_optimize: 10

# 模型特定配置
model_compression:
  "claude":
    mode: aggressive
    preserve_structure: false
    max_compression_ratio: 0.7
  "gpt":
    mode: normal
    preserve_structure: true
    max_compression_ratio: 0.5
  "llama":
    mode: soft
    preserve_structure: true
    max_compression_ratio: 0.3
```

### 编程配置

```python
optimizer = TokenOptimizer(
    mode=CompressionMode.NORMAL,          # 压缩模式
    preserve_code=True,                    # 保护代码块
    max_compression_ratio=0.7,            # 最大压缩率
    min_tokens_to_optimize=10,            # 最小 Token 数
)
```

---

## 📊 7 阶段压缩管道详解

### Stage 1: 拼写修正 (Spell Correction)

**功能**：修复常见拼写错误，使用字典 + Norvig 算法

**保护规则**：
- ALL-CAPS 单词（如 `API`、`HTTP`）
- 首字母大写单词（如 `Python`、`JavaScript`）
- 包含数字的单词（如 `var1`、`func2`）
- 代码块内容（反引号内）

**示例**：
```
输入: "I dont know if this makes sense but could you maybe help me refacter the authetication module"
输出: "I don't know if this makes sense but could you maybe help me refactor the authentication module"
```

**词典规模**：200+ 常见编程和英语拼写错误

### Stage 2: 空白规范化 (Whitespace Normalization)

**功能**：清理多余空白、空行、缩进

**处理规则**：
- 多个空格 → 单个空格
- 3+ 空行 → 2 空行
- 行首尾空白 → 去除
- 代码块内容 → 保留原始缩进

**示例**：
```
输入: "Hello    world\n\n\n\nLine 2"
输出: "Hello world\n\nLine 2"
```

### Stage 3: 模式优化 (Pattern Optimization)

**功能**：去除填充词、犹豫语言、元语言

**130+ 规则**：
- 犹豫语言：`I don't know if`, `maybe`, `perhaps`
- 元语言：`As I mentioned`, `like I said`, `I think that`
- 填充词：`basically`, `essentially`, `literally`, `actually`
- 问题软化：`Could you perhaps`, `I was wondering if`

**示例**：
```
输入: "As I mentioned earlier, I think that this is basically important"
输出: "this is important"
```

### Stage 4: 冗余消除 (Redundancy Elimination)

**功能**：去除重复的句子、段落、内容

**处理规则**：
- 精确重复句子 → 保留一份
- 语义重复内容 → 合并
- 代码块 → 保留

**示例**：
```
输入: "Hello world. Hello world. This is a test. This is a test."
输出: "Hello world. This is a test."
```

### Stage 5: NLP 分析 (NLP Analysis)

**功能**：疑问句→祈使句转换，去除礼貌用语

**处理规则**：
- `Could you help me X` → `X`
- `Can you X` → `X`
- `Please X` → `X`
- `I want you to X` → `X`

**示例**：
```
输入: "Could you help me refactor the authentication module?"
输出: "refactor the authentication module?"
```

### Stage 6: 电报压缩 (Telegraph Compression)

**功能**：激进模式下的极致压缩

**处理规则**：
- 去除冠词：`a`, `an`, `the`
- 去除助动词：`is`, `are`, `was`, `were`
- 去除介词：`in`, `on`, `at`, `by`, `for`
- 去除连词：`and`, `or`, `but`, `because`
- 去除代词：`I`, `you`, `he`, `she`, `it`

**示例**：
```
输入: "The quick brown fox jumps over the lazy dog"
输出: "quick brown fox jumps lazy dog"
```

### Stage 7: 最终清理 (Final Cleanup)

**功能**：清理最终输出

**处理规则**：
- 去除首尾空白
- 修复双空格
- 修复多空行
- 去除短行首标点（<20 字符）

---

## 📈 预期效果

| 提示词类型 | 原始 Token | 压缩后 Token | 压缩率 |
|-----------|-----------|-------------|--------|
|  verbose 提示词 | 52 | 9 | 83% |
| Agent 调试提示词 | 276 | 149 | 46% |
| 代码审查提示词 | 180 | 95 | 47% |
| 清晰技术提示词 | 15 | 15 | 0% |
| 平均 | ~130 | ~67 | ~48% |

---

## 🔒 安全与隐私

- **100% 本地处理**：压缩在 OpenLLM 服务端完成，不依赖外部 API
- **代码保护**：反引号内的代码块、URL、内联代码不受压缩影响
- **可配置**：用户可选择压缩模式和强度
- **透明**：所有压缩操作可追溯，原始内容保留用于审计

---

## 📝 API 参考

### TokenOptimizer

```python
class TokenOptimizer:
    def __init__(
        self,
        mode: CompressionMode = CompressionMode.NORMAL,
        preserve_code: bool = True,
        max_compression_ratio: float = 0.7,
        min_tokens_to_optimize: int = 10,
    ): ...
    
    def optimize(self, prompt: str, model: str = None) -> OptimizedPrompt: ...
    def optimize_messages(self, messages: List[Dict], model: str = None) -> List[Dict]: ...
    def get_stats(self) -> Dict: ...
```

### OptimizedPrompt

```python
@dataclass
class OptimizedPrompt:
    original: str              # 原始提示词
    optimized: str             # 优化后提示词
    original_tokens: int       # 原始 Token 数
    optimized_tokens: int      # 优化后 Token 数
    savings: int               # 节省的 Token 数
    savings_pct: float         # 节省百分比
    stages_applied: List[str]  # 应用的阶段列表
    
    @property
    def is_significant(self) -> bool: ...  # 节省是否显著 (>10%)
```

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/test_token_optimizer.py -v

# 运行特定测试
python -m pytest tests/test_token_optimizer.py::TestTokenOptimizer::test_optimize_normal_mode -v
```

**测试结果**：36 passed ✓

---

## 📚 参考资料

- [LLMLingua (EMNLP 2023)](https://llmlingua.com/)
- [Norvig Spelling Correction](https://norvig.com/spell-correct.html)
- [Terse - Intelligent Token Optimizer](https://terseai.org/)
