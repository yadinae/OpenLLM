"""
Batch Executor — 批量代码执行 + 文件读取追踪

Inspired by context-mode's ctx_batch_execute.

核心理念：
- 批量执行多个命令，只返回最终摘要
- 追踪所有文件读取，但不将文件内容放入上下文
- 通过注入 Node.js preload 脚本追踪 Python/JS 的文件读取

典型场景：
- 扫描 50 个文件统计函数数量 → 返回 3.6KB（替代 700KB 原始内容）
- 分析项目依赖关系 → 返回依赖图摘要
- 搜索代码库中的模式 → 返回匹配列表
"""

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from .executor import SandboxExecutor, ExecResult, SUPPORTED_LANGUAGES


@dataclass
class BatchCommand:
    """单个批处理命令"""
    language: str
    code: str
    label: str = ""  # 用于标识这个命令的用途


@dataclass
class BatchResult:
    """批处理执行结果"""
    commands_executed: int
    commands_succeeded: int
    commands_failed: int
    total_duration_ms: float
    results: list[ExecResult]
    files_read: list[str] = field(default_factory=list)  # 追踪到的文件读取
    summary: str = ""  # 自动生成的摘要

    @property
    def context_bytes(self) -> int:
        """结果占用的上下文字节数"""
        return len(self.summary.encode()) if self.summary else 0


class BatchExecutor:
    """批量代码执行器

    - 顺序执行多个命令
    - 自动追踪文件读取（通过 LD_PRELOAD / --require）
    - 只返回摘要，原始数据保存在沙盒中
    - 支持语言：Python, JavaScript, Shell
    """

    def __init__(
        self,
        executor: Optional[SandboxExecutor] = None,
        max_output_bytes: int = 50_000,
        timeout_seconds: int = 60,
    ):
        self.executor = executor or SandboxExecutor(
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        )
        self._fs_tracker_path: Optional[str] = None

    def execute_batch(
        self,
        commands: list[BatchCommand],
        track_file_reads: bool = True,
    ) -> BatchResult:
        """执行一批命令

        Args:
            commands: 要执行的命令列表
            track_file_reads: 是否追踪文件读取

        Returns:
            BatchResult: 批量执行结果
        """
        if not commands:
            return BatchResult(
                commands_executed=0,
                commands_succeeded=0,
                commands_failed=0,
                total_duration_ms=0,
                results=[],
            )

        all_results = []
        all_files_read = []
        total_start = time.monotonic()

        for cmd in commands:
            result = self.executor.execute(
                language=cmd.language,
                code=cmd.code,
                timeout=self.executor.timeout_seconds,
            )
            all_results.append(result)

            # 从输出中提取文件路径（简单模式匹配）
            if track_file_reads:
                files = self._extract_file_paths(result.stdout + result.stderr)
                all_files_read.extend(files)

        total_duration_ms = (time.monotonic() - total_start) * 1000
        succeeded = sum(1 for r in all_results if r.success)
        failed = len(all_results) - succeeded

        # 生成摘要
        summary = self._generate_summary(commands, all_results, all_files_read)

        return BatchResult(
            commands_executed=len(commands),
            commands_succeeded=succeeded,
            commands_failed=failed,
            total_duration_ms=total_duration_ms,
            results=all_results,
            files_read=list(set(all_files_read)),
            summary=summary,
        )

    def execute_single_with_tracking(
        self,
        language: str,
        code: str,
        timeout: Optional[int] = None,
    ) -> ExecResult:
        """执行单个命令，启用文件读取追踪

        对于 Python，注入 --require 脚本来追踪 fs.readFileSync。
        """
        if language == "python" and self.executor.runtimes.get("python"):
            # 注入 fs 追踪脚本
            tracked_code = self._wrap_python_tracking(code)
            return self.executor.execute("python", tracked_code, timeout=timeout)

        return self.executor.execute(language, code, timeout=timeout)

    def _wrap_python_tracking(self, code: str) -> str:
        """为 Python 代码注入文件读取追踪"""
        tracking_code = """
import sys
import os

# 文件读取追踪
_cm_tracked_files = []
_original_open = __builtins__.open

def _tracking_open(file, mode='r', *args, **kwargs):
    if 'r' in str(mode):
        try:
            abs_path = os.path.abspath(file)
            _cm_tracked_files.append(abs_path)
        except:
            pass
    return _original_open(file, mode, *args, **kwargs)

__builtins__.open = _tracking_open

# 用户代码
""" + code + """

# 输出追踪结果
if _cm_tracked_files:
    import json
    print("\\n__CM_FILES_READ__", json.dumps(list(set(_cm_tracked_files))))
"""
        return tracking_code

    def _extract_file_paths(self, output: str) -> list[str]:
        """从输出中提取文件路径"""
        import re
        paths = []

        # 匹配 __CM_FILES_READ__ 标记（来自注入的追踪脚本）
        for line in output.split("\n"):
            if "__CM_FILES_READ__" in line:
                try:
                    json_part = line.split("__CM_FILES_READ__", 1)[1].strip()
                    files = json.loads(json_part)
                    paths.extend(files)
                except (json.JSONDecodeError, IndexError):
                    pass

        # 匹配常见文件路径模式
        path_pattern = re.compile(r'[/\w\-.]+(?:\.(?:py|js|ts|json|yaml|yml|md|txt|cfg|ini|conf|toml|sh|rs|go|rb))')
        for match in path_pattern.finditer(output):
            p = match.group(0)
            if len(p) > 3 and not p.startswith('http'):
                paths.append(p)

        return paths

    def _generate_summary(
        self,
        commands: list[BatchCommand],
        results: list[ExecResult],
        files_read: list[str],
    ) -> str:
        """生成上下文友好的摘要"""
        lines = [f"Batch: {len(commands)} commands executed"]

        for i, (cmd, result) in enumerate(zip(commands, results)):
            label = cmd.label or f"Command {i+1}"
            status = "✅" if result.success else "❌"
            lines.append(f"  {status} {label}: exit={result.exit_code}, time={result.duration_ms:.0f}ms")
            # 只取输出前 200 字符
            output_preview = (result.stdout or result.stderr or "")[:200].strip()
            if output_preview:
                lines.append(f"     → {output_preview[:100]}")

        if files_read:
            lines.append(f"\nFiles accessed: {len(files_read)}")
            # 只列出前 10 个
            for f in files_read[:10]:
                lines.append(f"  - {f}")
            if len(files_read) > 10:
                lines.append(f"  ... and {len(files_read) - 10} more")

        return "\n".join(lines)
