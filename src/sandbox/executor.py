"""
Sandbox Executor — 多语言代码执行器

Inspired by context-mode's PolyglotExecutor.
Executes code in isolated temp directories, captures output, truncates to save context.

核心理念：LLM 应该生成代码来分析数据，而不是直接在上下文中处理数据。
1 个脚本执行 = 替代 10 次工具调用，节省 100x 上下文。
"""

import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Data classes
# ============================================================

@dataclass
class ExecResult:
    """执行结果 — 替代原始大量输出，只返回摘要"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    # Context saving metrics
    raw_bytes: int = 0          # 原始输出大小
    truncated: bool = False      # 是否被截断
    languages_available: list = field(default_factory=list)
    files_read: list = field(default_factory=list)  # batch 模式下追踪的文件读取

    @property
    def summary(self) -> str:
        """生成摘要 — 只返回关键信息，节省上下文"""
        lines = [f"exit_code={self.exit_code}", f"duration={self.duration_ms:.0f}ms"]
        if self.stdout:
            lines.append(f"stdout: {self.stdout[:500]}")
        if self.stderr:
            lines.append(f"stderr: {self.stderr[:500]}")
        if self.files_read:
            lines.append(f"files_read: {len(self.files_read)} files")
        return "\n".join(lines)


# ============================================================
# Language definitions
# ============================================================

SUPPORTED_LANGUAGES = {
    "python": {"ext": "py", "cmds": [["python3"], ["python"]]},
    "javascript": {"ext": "js", "cmds": [["node"]]},
    "typescript": {"ext": "ts", "cmds": [["npx", "tsx"], ["npx", "ts-node"], ["deno", "run"], ["bun", "run"]]},
    "shell": {"ext": "sh", "cmds": [["bash"], ["sh"]]},
    "ruby": {"ext": "rb", "cmds": [["ruby"]]},
    "perl": {"ext": "pl", "cmds": [["perl"]]},
    "php": {"ext": "php", "cmds": [["php"]]},
    "go": {"ext": "go", "cmds": [["go", "run"]]},
    "rust": {"ext": "rs", "cmds": [["rustc"]]},  # compile then run
}


def detect_runtimes() -> dict[str, list[str]]:
    """检测系统已安装的语言运行时"""
    available = {}
    for lang, info in SUPPORTED_LANGUAGES.items():
        for cmd in info["cmds"]:
            try:
                result = subprocess.run(
                    cmd + ["--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    available[lang] = cmd
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
    return available


# ============================================================
# Core Executor
# ============================================================

class SandboxExecutor:
    """多语言沙盒执行器

    - 每个执行创建独立的临时目录，防止文件污染
    - 输出自动截断，防止大输出淹没上下文窗口
    - 超时自动终止，防止无限循环
    - 可选追踪文件读取（用于上下文感知）
    """

    def __init__(
        self,
        max_output_bytes: int = 50_000,   # 最大输出 50KB
        timeout_seconds: int = 30,         # 默认 30s 超时
        project_root: Optional[str] = None,
    ):
        self.max_output_bytes = max_output_bytes
        self.timeout_seconds = timeout_seconds
        self._project_root = project_root or os.getcwd()
        self._runtimes = detect_runtimes()

    @property
    def runtimes(self) -> dict[str, list[str]]:
        return dict(self._runtimes)

    def execute(
        self,
        language: str,
        code: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> ExecResult:
        """执行代码

        Args:
            language: 语言名 (python, javascript, shell, etc.)
            code: 要执行的代码
            timeout: 超时秒数 (默认使用构造函数设置)
            cwd: 工作目录 (默认使用临时目录)
            env: 环境变量 (会自动清理危险变量)

        Returns:
            ExecResult: 执行结果
        """
        timeout = timeout or self.timeout_seconds

        if language not in self._runtimes:
            return ExecResult(
                success=False,
                stdout="",
                stderr=f"Language '{language}' not available. Available: {list(self._runtimes.keys())}",
                exit_code=-1,
                duration_ms=0,
            )

        # 创建临时目录
        with tempfile.TemporaryDirectory(prefix="openllm-sandbox-") as tmpdir:
            # 写入脚本文件
            ext = SUPPORTED_LANGUAGES[language]["ext"]
            script_path = os.path.join(tmpdir, f"script.{ext}")
            with open(script_path, "w") as f:
                f.write(code)

            # 构建命令
            cmd = self._runtimes[language] + [script_path]

            # 构建安全环境
            safe_env = self._build_safe_env(env)

            # 执行
            start = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd or tmpdir,
                    env=safe_env,
                )
                duration_ms = (time.monotonic() - start) * 1000

                raw_bytes = len(proc.stdout.encode()) + len(proc.stderr.encode())
                stdout, stdout_truncated = self._truncate(proc.stdout)
                stderr, stderr_truncated = self._truncate(proc.stderr)

                return ExecResult(
                    success=proc.returncode == 0,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=proc.returncode,
                    duration_ms=duration_ms,
                    raw_bytes=raw_bytes,
                    truncated=stdout_truncated or stderr_truncated,
                )

            except subprocess.TimeoutExpired:
                duration_ms = (time.monotonic() - start) * 1000
                return ExecResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out after {timeout}s",
                    exit_code=-1,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000
                return ExecResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution error: {str(e)}",
                    exit_code=-1,
                    duration_ms=duration_ms,
                )

    def _truncate(self, text: str) -> tuple[str, bool]:
        """截断输出，保留头部和尾部"""
        if len(text.encode()) <= self.max_output_bytes:
            return text, False

        max_bytes = self.max_output_bytes // 2  # split between head and tail
        encoded = text.encode()

        head = encoded[:max_bytes].decode("utf-8", errors="ignore")
        tail = encoded[-max_bytes:].decode("utf-8", errors="ignore")

        truncated = f"\n--- [OUTPUT TRUNCATED: {len(text.encode())} bytes, showing head and tail] ---\n"
        return head + truncated + tail, True

    def _build_safe_env(self, extra: Optional[dict] = None) -> dict:
        """构建安全环境变量 — 清除敏感信息"""
        # 只保留必要的环境变量
        safe_keys = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR", "PYTHONPATH", "NODE_PATH"}
        env = {k: v for k, v in os.environ.items() if k in safe_keys}

        # 确保 PATH 存在
        if "PATH" not in env:
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin"

        # 合并额外变量
        if extra:
            env.update(extra)

        return env

    def get_available_languages(self) -> list[str]:
        """获取可用的语言列表"""
        return list(self._runtimes.keys())

    def get_runtime_summary(self) -> dict:
        """获取运行时摘要"""
        return {
            "available": list(self._runtimes.keys()),
            "total_supported": len(SUPPORTED_LANGUAGES),
            "total_available": len(self._runtimes),
        }
