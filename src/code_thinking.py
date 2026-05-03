"""
Code Thinking — "Think in Code" 系统提示增强器

Inspired by context-mode's "Think in Code" paradigm.

核心理念：
LLM 应该生成代码来分析数据，而不是直接在上下文中处理数据。
Instead of reading 50 files into context to count functions,
the agent writes a script that does the counting and returns only the result.
One script replaces ten tool calls and saves 100x context.

使用方式：
- 在 system prompt 中注入 "code thinking" 指令
- 自动检测任务类型，决定是否启用
- 可配合 sandbox 工具使用（/api/sandbox/execute）

配置：
- code_thinking.auto_enable: 自动检测任务类型并启用
- code_thinking.system_prompt: 自定义 system prompt
- code_thinking.trigger_keywords: 触发代码思维的任务关键词
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 系统提示模板
# ============================================================

CODE_THINKING_SYSTEM_PROMPT = """\
## Code Thinking Mode

You think in code, not prose. When analyzing data, files, or complex information:

1. **Write code to analyze** — Don't read data into context. Write a script that processes it and returns only results.
2. **Script over manual** — One script that counts, searches, or transforms replaces dozens of manual tool calls.
3. **Return results only** — The script's output (numbers, lists, summaries) goes into context. Raw data stays in files.
4. **Think step-by-step in code** — Break analysis into executable steps, not paragraphs of reasoning.

### Examples

❌ Don't: Read 50 files into context, then manually count functions per file.
✅ Do: Write a script that scans files and prints "file.py: 23 functions" for each.

❌ Don't: Search through 1000 lines of logs in context for error patterns.
✅ Do: Write a grep/regex script that outputs matching lines with counts.

### When to use

- Scanning multiple files or directories
- Analyzing large datasets, logs, or API responses
- Counting, aggregating, or transforming data
- Finding patterns across a codebase
- Any task where manual data processing would consume significant context

### Available tools

If sandbox tools are available, use them:
- `execute` — Run code in isolated sandbox (Python, JavaScript, Shell)
- `batch_execute` — Run multiple commands, get summary only
- `index` — Store large content for later search retrieval
- `search` — BM25 search indexed content

Always prefer code analysis over manual context processing.\
"""

# 中文版
CODE_THINKING_SYSTEM_PROMPT_CN = """\
## 代码思维模式

你使用代码来分析数据，而不是直接在上下文中处理信息。

1. **用代码分析** — 不要把大量数据读入上下文。写脚本来处理，只返回结果。
2. **脚本优于手动** — 一个脚本可以替代几十次手动工具调用。
3. **只返回结果** — 脚本的输出（数字、列表、摘要）进入上下文，原始数据留在文件中。
4. **用代码逐步思考** — 将分析拆分为可执行的步骤，而不是一段段推理。

### 何时使用

- 扫描多个文件或目录
- 分析大型数据集、日志或 API 响应
- 计数、聚合或转换数据
- 在代码库中查找模式
- 任何手动数据处理会消耗大量上下文的场景\
"""


# ============================================================
# 触发关键词
# ============================================================

TRIGGER_KEYWORDS_EN = {
    # 扫描/分析任务
    "count", "scan", "analyze", "search", "find all", "list all",
    # 数据处理
    "aggregate", "summarize", "transform", "extract", "filter",
    # 代码库操作
    "throughout the codebase", "in all files", "every file", "all functions",
    "all classes", "all imports", "all dependencies",
    # 日志/数据
    "log file", "access log", "error log", "dataset", "csv", "json file",
    "large file", "multiple files", "directory", "folder",
    # 数量/统计
    "how many", "total count", "number of", "statistics", "frequency",
    # 模式查找
    "pattern", "pattern matching", "find occurrences", "where is",
    # 重构/批量操作
    "refactor", "rename all", "replace all", "update all", "batch",
}

TRIGGER_KEYWORDS_CN = {
    "统计", "扫描", "分析", "搜索", "查找所有", "列出所有",
    "汇总", "提取", "筛选", "代码库", "所有文件", "每个文件",
    "所有函数", "所有类", "所有依赖", "日志文件", "数据集",
    "大文件", "多个文件", "目录", "多少个", "总数", "数量",
    "频率", "模式", "查找出现", "批量", "重构", "重命名所有",
    "替换所有", "更新所有",
}

ALL_TRIGGER_KEYWORDS = TRIGGER_KEYWORDS_EN | TRIGGER_KEYWORDS_CN


# ============================================================
# CodeThinkingInjector
# ============================================================

class CodeThinkingInjector:
    """代码思维系统提示注入器

    自动检测任务类型，在 system prompt 中注入代码思维指令。
    """

    def __init__(
        self,
        auto_enable: bool = True,
        system_prompt: Optional[str] = None,
        trigger_keywords: Optional[set[str]] = None,
        language: str = "en",
    ):
        self.auto_enable = auto_enable
        self.system_prompt = system_prompt or (
            CODE_THINKING_SYSTEM_PROMPT_CN if language == "zh"
            else CODE_THINKING_SYSTEM_PROMPT
        )
        self.trigger_keywords = trigger_keywords or ALL_TRIGGER_KEYWORDS

    def should_enable(self, messages: list[dict]) -> bool:
        """检测是否应该启用代码思维模式

        检查用户消息中是否包含触发关键词。
        """
        if not self.auto_enable:
            return False

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if any(kw.lower() in content for kw in self.trigger_keywords):
                    return True

        return False

    def inject(self, messages: list[dict], force: bool = False) -> tuple[list[dict], bool]:
        """注入代码思维系统提示

        Args:
            messages: 消息列表
            force: 是否强制注入（忽略自动检测）

        Returns:
            (增强后的消息列表, 是否注入了提示)
        """
        if not force and not self.should_enable(messages):
            return messages, False

        # 检查是否已经有代码思维提示
        for msg in messages:
            if msg.get("role") == "system" and "Code Thinking" in msg.get("content", ""):
                return messages, False

        # 构建注入内容
        injection = "\n\n" + self.system_prompt

        # 找到第一个 system message 并注入
        enhanced = []
        injected = False
        for msg in messages:
            if msg.get("role") == "system" and not injected:
                enhanced.append({
                    "role": "system",
                    "content": msg.get("content", "") + injection,
                })
                injected = True
            else:
                enhanced.append(msg)

        # 如果没有 system message，创建一个新的
        if not injected:
            enhanced.insert(0, {
                "role": "system",
                "content": self.system_prompt,
            })
            injected = True

        logger.info(f"Code Thinking mode {'enabled' if injected else 'skipped'}")
        return enhanced, injected

    def get_prompt(self) -> str:
        """获取系统提示文本"""
        return self.system_prompt


# ============================================================
# Global instance
# ============================================================

_injector: Optional[CodeThinkingInjector] = None


def get_injector(config: Optional[dict] = None) -> CodeThinkingInjector:
    """获取全局注入器实例"""
    global _injector
    if _injector is None:
        cfg = config or {}
        _injector = CodeThinkingInjector(
            auto_enable=cfg.get("auto_enable", True),
            system_prompt=cfg.get("system_prompt"),
            language=cfg.get("language", "en"),
        )
    return _injector


def reset_injector():
    """重置全局实例"""
    global _injector
    _injector = None
